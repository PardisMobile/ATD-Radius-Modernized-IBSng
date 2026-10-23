"""Read-only preflight for assessing an existing IBSng A1.24 database.

This command never modifies the target database and does not stamp migrations.
A clean report is necessary but not sufficient for adoption: it does not compare
all constraint semantics, extension/plugin objects, every application datum, or
prove backup/restore fidelity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

CANONICAL_A124_SHA256 = "c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8"
_REQUIRED_FILES = (
    "IBSng/db/tables.sql",
    "IBSng/db/functions.sql",
    "IBSng/db/initial.sql",
    "IBSng/db/defs.sql",
)
_CREATE_TABLE = re.compile(r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?([a-z_][\w$]*)\s*\(", re.I)
_CREATE_INDEX = re.compile(r"\bcreate\s+(?:unique\s+)?index\s+([a-z_][\w$]*)\s+on\s+([a-z_][\w$]*)\b", re.I)
_CREATE_SEQUENCE = re.compile(r"\bcreate\s+sequence\s+([a-z_][\w$]*)\b", re.I)
_CREATE_FUNCTION = re.compile(r"\bcreate\s+(?:or\s+replace\s+)?function\s+([a-z_][\w$]*)\s*\(", re.I)
_SERIAL = re.compile(r"^(?:smallserial|serial|bigserial)\b", re.I)
_CONSTRAINT = re.compile(r"^(?:constraint\s+\S+\s+)?(?:primary\s+key|foreign\s+key|unique|check|exclude)\b", re.I)


def _strip_line_comments(sql: str) -> str:
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 1
                else:
                    quote = None
        elif ch == "'":
            quote = ch
            out.append(ch)
        elif ch == "-" and i + 1 < len(sql) and sql[i + 1] == "-":
            while i < len(sql) and sql[i] != "\n":
                i += 1
            out.append("\n")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _split_top_level(text: str) -> list[str]:
    items: list[str] = []
    start = depth = 0
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif ch == "'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            items.append(text[start:i].strip())
            start = i + 1
        i += 1
    if text[start:].strip():
        items.append(text[start:].strip())
    return items


def _table_bodies(sql: str) -> list[tuple[str, str]]:
    cleaned = _strip_line_comments(sql)
    found: list[tuple[str, str]] = []
    for match in _CREATE_TABLE.finditer(cleaned):
        depth, quote, i, start = 1, None, match.end(), match.end()
        while i < len(cleaned) and depth:
            ch = cleaned[i]
            if quote:
                if ch == quote:
                    if i + 1 < len(cleaned) and cleaned[i + 1] == quote:
                        i += 1
                    else:
                        quote = None
            elif ch == "'":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        if depth:
            raise ValueError(f"Unterminated CREATE TABLE for {match.group(1)}")
        found.append((match.group(1).lower(), cleaned[start:i - 1]))
    if not found:
        raise ValueError("No CREATE TABLE statements found in canonical A1.24 tables.sql")
    if len({name for name, _ in found}) != len(found):
        raise ValueError("Duplicate CREATE TABLE names in canonical A1.24 schema")
    return found



def _normalize_default(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    while len(normalized) > 1 and normalized[0] == "(" and normalized[-1] == ")":
        normalized = normalized[1:-1].strip()
    normalized = re.sub(r"^'(t|true)'(?:::[a-z_][\w ]*)?$", "true", normalized)
    normalized = re.sub(r"^'(f|false)'(?:::[a-z_][\w ]*)?$", "false", normalized)
    return normalized


def _source_column_spec(declaration: str, table_primary_key: bool = False) -> dict[str, Any]:
    default_match = re.search(
        r"\bdefault\s+(.+?)(?=\s+(?:not\s+null|primary\s+key|unique|references|check)\b|$)",
        declaration, re.I,
    )
    type_part = re.split(
        r"\b(?:default|not\s+null|null|primary\s+key|unique|references|check|collate|generated)\b",
        declaration, maxsplit=1, flags=re.I,
    )[0].strip()
    type_name = re.sub(r"\s+", " ", type_part).lower()
    aliases = {
        "serial": "integer", "smallserial": "smallint", "bigserial": "bigint",
        "int": "integer", "int4": "integer", "int8": "bigint", "int2": "smallint",
        "bool": "boolean", "char": "character",
        "timestamp": "timestamp without time zone", "time": "time without time zone",
    }
    for alias, canonical in aliases.items():
        if type_name == alias:
            type_name = canonical
            break
        if type_name.startswith(alias + "("):
            type_name = canonical + type_name[len(alias):]
            break
    serial_type = bool(_SERIAL.match(declaration))
    return {
        "type": type_name,
        "nullable": not bool(re.search(r"\bnot\s+null\b|\bprimary\s+key\b", declaration, re.I) or table_primary_key),
        "default": None if serial_type else _normalize_default(default_match.group(1) if default_match else None),
        "serial": serial_type,
    }


def _normalize_type(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    aliases = {
        "int": "integer", "int4": "integer", "int8": "bigint", "int2": "smallint",
        "bool": "boolean", "timestamp": "timestamp without time zone",
        "time": "time without time zone",
    }
    return aliases.get(normalized, normalized)


def _function_signatures(functions_sql: str) -> set[tuple[str, tuple[str, ...]]]:
    cleaned = _strip_line_comments(functions_sql)
    signatures: set[tuple[str, tuple[str, ...]]] = set()
    for match in _CREATE_FUNCTION.finditer(cleaned):
        depth, quote, i, start = 1, None, match.end(), match.end()
        while i < len(cleaned) and depth:
            ch = cleaned[i]
            if quote:
                if ch == quote:
                    if i + 1 < len(cleaned) and cleaned[i + 1] == quote:
                        i += 1
                    else:
                        quote = None
            elif ch == "'":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        if depth:
            raise ValueError(f"Unterminated function argument list for {match.group(1)}")
        args = tuple(_normalize_type(arg) for arg in _split_top_level(cleaned[start:i - 1]) if arg.strip())
        signatures.add((match.group(1).lower(), args))
    if not signatures:
        raise ValueError("No function signatures found in canonical A1.24 functions.sql")
    return signatures

def _normalize_rule_condition(condition: str) -> str:
    """Normalize PostgreSQL's display-only parentheses, whitespace, and common type casts."""
    normalized = re.sub(r"\s+", "", condition).lower()
    normalized = re.sub(r"\)::(?:text|integer|bigint|smallint|boolean)\b", ")", normalized)
    normalized = re.sub(r"::(?:text|integer|bigint|smallint|boolean)\b", "", normalized)
    return normalized.replace("(", "").replace(")", "")


def _normalize_check_expression(expression: str) -> str:
    """Normalize spacing/casts while preserving meaningful nested CHECK parentheses."""
    normalized = re.sub(r"\s+", "", expression).lower()
    normalized = re.sub(r"::(?:text|integer|bigint|smallint|boolean)\b", "", normalized)
    while normalized.startswith("(") and normalized.endswith(")"):
        depth = 0
        wraps_entire_expression = True
        for index, char in enumerate(normalized):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(normalized) - 1:
                    wraps_entire_expression = False
                    break
        if not wraps_entire_expression:
            break
        normalized = normalized[1:-1]
    return normalized


def _source_rules(initial_sql: str) -> dict[str, dict[str, str]]:
    """Extract the two simple, source-defined A1.24 protection rules."""
    cleaned = _strip_line_comments(initial_sql)
    pattern = re.compile(
        r"create\s+rule\s+([a-z_][\w$]*)\s+as\s+on\s+(delete|update|insert)\s+"
        r"to\s+([a-z_][\w$]*)\s+where\s+(.+?)\s+do\s+instead\s+nothing\s*;",
        re.I | re.S,
    )
    rules: dict[str, dict[str, str]] = {}
    for match in pattern.finditer(cleaned):
        name, event, table, condition = match.groups()
        rules[name.lower()] = {
            "event": event.upper(),
            "table": table.lower(),
            "condition": _normalize_rule_condition(condition),
            "action": "INSTEAD NOTHING",
        }
    if not rules:
        raise ValueError("No supported source protection rules found in canonical A1.24 initial.sql")
    return rules


def _function_definitions(functions_sql: str) -> dict[tuple[str, tuple[str, ...]], str]:
    """Extract decoded SQL-language function bodies from the canonical A1.24 file."""
    cleaned = _strip_line_comments(functions_sql)
    definitions: dict[tuple[str, tuple[str, ...]], str] = {}
    for match in _CREATE_FUNCTION.finditer(cleaned):
        depth, quote, i, start = 1, None, match.end(), match.end()
        while i < len(cleaned) and depth:
            ch = cleaned[i]
            if quote:
                if ch == quote:
                    if i + 1 < len(cleaned) and cleaned[i + 1] == quote:
                        i += 1
                    else:
                        quote = None
            elif ch == "'":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        if depth:
            raise ValueError(f"Unterminated function argument list for {match.group(1)}")
        args = tuple(
            _normalize_type(arg) for arg in _split_top_level(cleaned[start:i - 1]) if arg.strip()
        )
        body_match = re.search(r"\bas\s*'", cleaned[i:], re.I)
        if body_match is None:
            raise ValueError(f"Missing quoted function body for {match.group(1)}")
        body_start = i + body_match.end()
        j = body_start
        body_chars: list[str] = []
        while j < len(cleaned):
            if cleaned[j] == "'":
                if j + 1 < len(cleaned) and cleaned[j + 1] == "'":
                    body_chars.append("'")
                    j += 2
                    continue
                break
            body_chars.append(cleaned[j])
            j += 1
        if j >= len(cleaned):
            raise ValueError(f"Unterminated quoted function body for {match.group(1)}")
        key = (match.group(1).lower(), args)
        if key in definitions:
            raise ValueError(f"Duplicate function definition: {key[0]}{key[1]}")
        definitions[key] = "".join(body_chars).strip()
    if not definitions:
        raise ValueError("No function bodies found in canonical A1.24 functions.sql")
    return definitions


def _normalize_index_sql(expression: str | None) -> str:
    """Normalize the limited expression/predicate forms used by canonical A1.24 indexes."""
    if not expression:
        return ""
    normalized = re.sub(r"\s+", "", expression).lower()
    normalized = re.sub(
        r"cast\((.+?)as(smallint|integer|bigint|text|boolean)\)",
        r"(\1)::\2",
        normalized,
    )
    normalized = re.sub(r"::(?:text|integer|bigint|smallint|boolean)\b", "", normalized)
    normalized = re.sub(
        r"([a-z_][\w$]*)in\(([^()]*)\)",
        r"\1=any(array[\2])",
        normalized,
    )
    normalized = re.sub(r"\)::(?:text|integer|bigint|smallint|boolean)\[\]", ")", normalized)
    while normalized.startswith("(") and normalized.endswith(")"):
        depth = 0
        wraps_all = True
        for index, char in enumerate(normalized):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(normalized) - 1:
                    wraps_all = False
                    break
        if not wraps_all:
            break
        normalized = normalized[1:-1]
    return normalized


def _source_index_details(tables_sql: str) -> dict[str, dict[str, Any]]:
    """Inventory source explicit-index shape without pretending to compare expression text."""
    cleaned = _strip_line_comments(tables_sql)
    pattern = re.compile(
        r"\bcreate\s+(?P<unique>unique\s+)?index\s+(?P<name>[a-z_][\w$]*)\s+"
        r"on\s+(?P<table>[a-z_][\w$]*)\b",
        re.I,
    )
    details: dict[str, dict[str, Any]] = {}
    for match in pattern.finditer(cleaned):
        open_paren = cleaned.find("(", match.end())
        if open_paren < 0:
            raise ValueError(f"Missing index column list for {match.group('name')}")
        depth, quote, i = 1, None, open_paren + 1
        while i < len(cleaned) and depth:
            char = cleaned[i]
            if quote:
                if char == quote:
                    if i + 1 < len(cleaned) and cleaned[i + 1] == quote:
                        i += 1
                    else:
                        quote = None
            elif char == "'":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            i += 1
        if depth:
            raise ValueError(f"Unterminated index column list for {match.group('name')}")
        indexed_items = _split_top_level(cleaned[open_paren + 1:i - 1])
        prefix = cleaned[match.end():open_paren]
        method_match = re.search(r"\busing\s+([a-z_][\w$]*)", prefix, re.I)
        tail_end = cleaned.find(";", i)
        if tail_end < 0:
            tail_end = len(cleaned)
        tail = cleaned[i:tail_end]
        if match.group("name").lower() in details:
            raise ValueError(f"Duplicate explicit index in canonical A1.24 schema: {match.group('name')}")
        details[match.group("name").lower()] = {
            "table": match.group("table").lower(),
            "unique": bool(match.group("unique")),
            "partial": bool(re.search(r"\bwhere\b", tail, re.I)),
            "expression": any("(" in item for item in indexed_items),
            "key_count": len(indexed_items),
            "method": method_match.group(1).lower() if method_match else "btree",
            "expression_sql": _normalize_index_sql(
                ", ".join(item for item in indexed_items if "(" in item)
            ),
            "predicate_sql": _normalize_index_sql(
                re.search(r"\bwhere\s+(.+)$", tail, re.I | re.S).group(1)
                if re.search(r"\bwhere\s+(.+)$", tail, re.I | re.S) else ""
            ),
        }
    return details


def _source_constraint_signatures(tables_sql: str) -> set[tuple[Any, ...]]:
    """Extract table-level and inline PK/UNIQUE/FK/CHECK semantics from A1.24 DDL."""
    table_bodies = _table_bodies(tables_sql)
    declarations_by_table = {
        table: _split_top_level(body) for table, body in table_bodies
    }
    primary_keys: dict[str, tuple[str, ...]] = {}
    for table, declarations in declarations_by_table.items():
        for declaration in declarations:
            clean = re.sub(r"^constraint\s+[^\s]+\s+", "", declaration.strip(), flags=re.I)
            table_pk = re.match(r"^primary\s+key\s*\(([^)]+)\)", clean, re.I)
            if table_pk:
                primary_keys[table] = tuple(
                    item.strip().strip('"').lower() for item in table_pk.group(1).split(",")
                )
                break
            column_match = re.match(r"^([a-z_][\w$]*)\s+(.+)", declaration, re.I | re.S)
            if column_match and re.search(r"\bprimary\s+key\b", column_match.group(2), re.I):
                primary_keys[table] = (column_match.group(1).lower(),)
                break

    signatures: set[tuple[Any, ...]] = set()
    for table, declarations in declarations_by_table.items():
        for declaration in declarations:
            clean = re.sub(r"^constraint\s+[^\s]+\s+", "", declaration.strip(), flags=re.I)
            table_pk = re.match(r"^primary\s+key\s*\(([^)]+)\)", clean, re.I)
            table_unique = re.match(r"^unique\s*\(([^)]+)\)", clean, re.I)
            table_fk = re.match(
                r"^foreign\s+key\s*\(([^)]+)\)\s*references\s+"
                r"([a-z_][\w$]*)(?:\s*\(([^)]+)\))?",
                clean, re.I | re.S,
            )
            table_check = re.match(r"^check\s*\((.*)\)$", clean, re.I | re.S)
            if table_pk:
                columns = tuple(item.strip().strip('"').lower() for item in table_pk.group(1).split(","))
                signatures.add((table, "p", columns, None, (), None))
                continue
            if table_unique:
                columns = tuple(item.strip().strip('"').lower() for item in table_unique.group(1).split(","))
                signatures.add((table, "u", columns, None, (), None))
                continue
            if table_fk:
                columns = tuple(item.strip().strip('"').lower() for item in table_fk.group(1).split(","))
                ref_table = table_fk.group(2).lower()
                ref_columns = tuple(
                    item.strip().strip('"').lower() for item in table_fk.group(3).split(",")
                ) if table_fk.group(3) else primary_keys.get(ref_table, ())
                signatures.add((table, "f", columns, ref_table, ref_columns, None))
                continue
            if table_check:
                signatures.add((table, "c", (), None, (), _normalize_check_expression(table_check.group(1))))
                continue
            if _CONSTRAINT.match(declaration):
                continue

            column_match = re.match(r"^([a-z_][\w$]*)\s+(.+)", declaration, re.I | re.S)
            if not column_match:
                continue
            column, definition = column_match.group(1).lower(), column_match.group(2)
            if re.search(r"\bprimary\s+key\b", definition, re.I):
                signatures.add((table, "p", (column,), None, (), None))
            if re.search(r"\bunique\b", definition, re.I):
                signatures.add((table, "u", (column,), None, (), None))
            ref_match = re.search(
                r"\breferences\s+([a-z_][\w$]*)(?:\s*\(([^)]+)\))?",
                definition, re.I,
            )
            if ref_match:
                ref_table = ref_match.group(1).lower()
                ref_columns = tuple(
                    item.strip().strip('"').lower() for item in ref_match.group(2).split(",")
                ) if ref_match.group(2) else primary_keys.get(ref_table, ())
                signatures.add((table, "f", (column,), ref_table, ref_columns, None))
            check_match = re.search(r"\bcheck\s*\((.*)\)", definition, re.I | re.S)
            if check_match:
                signatures.add((table, "c", (), None, (), _normalize_check_expression(check_match.group(1))))
    return signatures


def source_inventory(tables_sql: str, functions_sql: str, initial_sql: str = "") -> dict[str, Any]:
    tables: dict[str, set[str]] = {}
    sequences = {m.group(1).lower() for m in _CREATE_SEQUENCE.finditer(_strip_line_comments(tables_sql))}
    indexes = {m.group(1).lower() for m in _CREATE_INDEX.finditer(_strip_line_comments(tables_sql))}
    column_specs: dict[tuple[str, str], dict[str, Any]] = {}
    for table, body in _table_bodies(tables_sql):
        columns: set[str] = set()
        declarations = _split_top_level(body)
        table_primary_keys: set[str] = set()
        for declaration in declarations:
            primary = re.match(r"^primary\s+key\s*\(([^)]+)\)", declaration, re.I)
            if primary:
                table_primary_keys.update(part.strip().strip('"').lower() for part in primary.group(1).split(","))
        for declaration in declarations:
            if not declaration or _CONSTRAINT.match(declaration):
                continue
            match = re.match(r"^([a-z_][A-Za-z0-9_$]*)\s+(.+)", declaration, re.I | re.S)
            if not match:
                raise ValueError(f"Cannot parse A1.24 column in {table}: {declaration!r}")
            name, definition = match.group(1).lower(), match.group(2)
            if name in columns:
                raise ValueError(f"Duplicate column {table}.{name}")
            columns.add(name)
            column_specs[(table, name)] = _source_column_spec(definition, name in table_primary_keys)
            if _SERIAL.match(definition):
                sequences.add(f"{table}_{name}_seq")
        tables[table] = columns
    function_definitions = _function_definitions(functions_sql)
    function_signatures = set(function_definitions)
    functions = {name for name, _ in function_signatures}
    function_body_sha256 = {
        key: hashlib.sha256(body.encode("utf-8")).hexdigest()
        for key, body in function_definitions.items()
    }
    sequence_owners = {
        f"{table}_{column}_seq": {"table": table, "column": column}
        for (table, column), spec in column_specs.items() if spec["serial"]
    }
    rules = _source_rules(initial_sql) if initial_sql.strip() else {}
    constraint_signatures = _source_constraint_signatures(tables_sql)
    index_details = _source_index_details(tables_sql)
    return {"tables": tables, "column_specs": column_specs, "indexes": indexes, "index_details": index_details, "sequences": sequences, "functions": functions, "function_signatures": function_signatures, "function_body_sha256": function_body_sha256, "sequence_owners": sequence_owners, "constraint_signatures": constraint_signatures, "rules": rules}


def _seed_values_equal(expected: Any, actual: Any, column_spec: dict[str, Any] | None = None) -> bool:
    # PostgreSQL CHAR(n) blank-pads values; compare the logical fixed-char value.
    if (
        column_spec
        and str(column_spec.get("type", "")).startswith("character(")
        and isinstance(expected, str)
        and isinstance(actual, str)
    ):
        return expected.rstrip() == actual.rstrip()
    return expected == actual


def _sql_literal_value(value: str) -> Any:
    token = value.strip()
    if len(token) >= 2 and token[0] == "'" and token[-1] == "'":
        return token[1:-1].replace("\\'", "'").replace("''", "'")
    if token.upper() == "NULL":
        return None
    if token.lower() in {"true", "false"}:
        return token.lower() == "true"
    if re.fullmatch(r"[+-]?\d+", token):
        return int(token)
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)", token):
        return Decimal(token)
    raise ValueError(f"Unsupported literal in canonical A1.24 seed: {token!r}")


def _source_table_column_order(tables_sql: str, target_table: str) -> list[str]:
    for table, body in _table_bodies(tables_sql):
        if table != target_table:
            continue
        columns: list[str] = []
        for declaration in _split_top_level(body):
            if not declaration or _CONSTRAINT.match(declaration):
                continue
            match = re.match(r"^([a-z_][A-Za-z0-9_$]*)\s+(.+)", declaration, re.I | re.S)
            if not match:
                raise ValueError(f"Cannot parse A1.24 column in {table}: {declaration!r}")
            columns.append(match.group(1).lower())
        return columns
    raise ValueError(f"Missing canonical A1.24 table: {target_table}")


def _initial_admin_seed(initial_sql: str, tables_sql: str) -> dict[str, Any]:
    matches = list(re.finditer(
        r"insert\s+into\s+admins\s+values\s*\((.*?)\)\s*;",
        _strip_line_comments(initial_sql), re.I | re.S,
    ))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one canonical admins seed row, found {len(matches)}")
    columns = _source_table_column_order(tables_sql, "admins")
    values = [_sql_literal_value(value) for value in _split_top_level(matches[0].group(1))]
    if len(columns) != len(values):
        raise ValueError(
            f"Canonical admins seed has {len(values)} values for {len(columns)} source columns"
        )
    return dict(zip(columns, values, strict=True))


def _initial_god_permission_seed(initial_sql: str) -> dict[str, Any]:
    match = re.search(
        r"insert\s+into\s+admin_perms\s*\(([^)]*)\)\s*values\s*\((.*?)\)\s*;",
        _strip_line_comments(initial_sql), re.I | re.S,
    )
    if match is None:
        raise ValueError("Missing canonical GOD permission seed in initial.sql")
    columns = [column.strip().lower() for column in match.group(1).split(",")]
    values = [_sql_literal_value(value) for value in _split_top_level(match.group(2))]
    if len(columns) != len(values) or "perm_name" not in columns:
        raise ValueError("Malformed canonical GOD permission seed in initial.sql")
    result = dict(zip(columns, values, strict=True))
    if result["perm_name"] != "GOD":
        raise ValueError("Canonical admin permission seed is not GOD")
    return result


def _initial_state_expectations(initial_sql: str) -> dict[str, str]:
    """Read every canonical IBS state seed from A1.24 initial.sql."""
    pattern = re.compile(
        r"insert\s+into\s+ibs_states\s+values\s*"
        r"\(\s*'((?:''|\\'|[^'])*)'\s*,\s*'((?:''|\\'|[^'])*)'\s*\)",
        re.I | re.S,
    )
    values: dict[str, str] = {}
    for match in pattern.finditer(_strip_line_comments(initial_sql)):
        name = match.group(1).replace("\\'", "'").replace("''", "'")
        value = match.group(2).replace("\\'", "'").replace("''", "'")
        if name in values:
            raise ValueError(f"Duplicate initial IBS state in canonical initial.sql: {name}")
        values[name] = value
    if not values:
        raise ValueError("No IBS state seeds found in canonical A1.24 initial.sql")
    return values


def _defs_expected(defs_sql: str) -> dict[str, str]:
    # SQL string literals support doubled apostrophes and embedded newlines.
    pattern = re.compile(
        r"insert\s+into\s+defs\s*\(\s*name\s*,\s*value\s*\)\s*values\s*"
        r"\(\s*'((?:''|\\'|[^'])*)'\s*,\s*'((?:''|\\'|[^'])*)'\s*\)",
        re.I | re.S,
    )
    values: dict[str, str] = {}
    for match in pattern.finditer(defs_sql):
        name = match.group(1).replace("\\'", "'").replace("''", "'")
        value = match.group(2).replace("\\'", "'").replace("''", "'")
        if name in values:
            raise ValueError(f"Duplicate definition in canonical defs.sql: {name}")
        values[name] = value
    if not values:
        raise ValueError("Could not parse definition rows from canonical defs.sql")
    return values


def _target_inventory(conn: psycopg.Connection, schema: str) -> dict[str, Any]:
    conn.execute("SELECT set_config('search_path', %s, true)", (f'"{schema.replace(chr(34), chr(34)*2)}", public',))
    tables = conn.execute(
        """
        SELECT c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND c.relkind IN ('r','p')
        ORDER BY c.relname
        """, (schema,)
    ).fetchall()
    columns = conn.execute(
        """
        SELECT c.relname, a.attname,
               pg_catalog.format_type(a.atttypid, a.atttypmod),
               NOT a.attnotnull,
               pg_catalog.pg_get_expr(d.adbin, d.adrelid)
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname=%s AND c.relkind IN ('r','p')
          AND a.attnum>0 AND NOT a.attisdropped AND a.attinhcount=0
        ORDER BY c.relname,a.attnum
        """, (schema,)
    ).fetchall()
    indexes = conn.execute(
        """
        SELECT ic.relname
        FROM pg_class tc JOIN pg_namespace n ON n.oid=tc.relnamespace
        JOIN pg_index i ON i.indrelid=tc.oid
        JOIN pg_class ic ON ic.oid=i.indexrelid
        LEFT JOIN pg_constraint co ON co.conindid=i.indexrelid
        WHERE n.nspname=%s AND tc.relkind IN ('r','p') AND co.oid IS NULL
        """, (schema,)
    ).fetchall()
    index_details = conn.execute(
        """
        SELECT ic.relname, tc.relname, i.indisunique, i.indpred IS NOT NULL,
               i.indexprs IS NOT NULL, am.amname, i.indnkeyatts,
               pg_get_expr(i.indexprs, i.indrelid, true),
               pg_get_expr(i.indpred, i.indrelid, true)
        FROM pg_class tc JOIN pg_namespace n ON n.oid=tc.relnamespace
        JOIN pg_index i ON i.indrelid=tc.oid
        JOIN pg_class ic ON ic.oid=i.indexrelid
        JOIN pg_am am ON am.oid=ic.relam
        LEFT JOIN pg_constraint co ON co.conindid=i.indexrelid
        WHERE n.nspname=%s AND tc.relkind IN ('r','p') AND co.oid IS NULL
        ORDER BY ic.relname
        """, (schema,)
    ).fetchall()
    sequences = conn.execute(
        "SELECT sequencename FROM pg_sequences WHERE schemaname=%s", (schema,)
    ).fetchall()
    functions = conn.execute(
        """
        SELECT DISTINCT p.proname, pg_get_function_identity_arguments(p.oid),
               p.prosrc
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname=%s
        """, (schema,)
    ).fetchall()
    constraints = conn.execute(
        """
        SELECT c.relname, co.conname, co.contype, pg_get_constraintdef(co.oid, true),
               ARRAY(
                 SELECT a.attname FROM unnest(co.conkey) WITH ORDINALITY k(attnum, ord)
                 JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum
                 ORDER BY k.ord
               ),
               rt.relname,
               ARRAY(
                 SELECT ra.attname FROM unnest(co.confkey) WITH ORDINALITY k(attnum, ord)
                 JOIN pg_attribute ra ON ra.attrelid=rt.oid AND ra.attnum=k.attnum
                 ORDER BY k.ord
               ),
               pg_get_expr(co.conbin, co.conrelid, true)
        FROM pg_constraint co
        JOIN pg_class c ON c.oid=co.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_class rt ON rt.oid=co.confrelid
        WHERE n.nspname=%s
        ORDER BY c.relname, co.conname
        """, (schema,)
    ).fetchall()
    rules = conn.execute(
        """
        SELECT c.relname, r.rulename, pg_get_ruledef(r.oid, true),
               CASE r.ev_type WHEN '1' THEN 'SELECT' WHEN '2' THEN 'UPDATE'
                    WHEN '3' THEN 'INSERT' WHEN '4' THEN 'DELETE' ELSE r.ev_type::text END,
               pg_get_expr(r.ev_qual, r.ev_class, true)
        FROM pg_rewrite r
        JOIN pg_class c ON c.oid=r.ev_class
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND r.rulename <> '_RETURN'
        ORDER BY c.relname, r.rulename
        """, (schema,)
    ).fetchall()
    triggers = conn.execute(
        """
        SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid, true)
        FROM pg_trigger t
        JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND NOT t.tgisinternal
        ORDER BY c.relname, t.tgname
        """, (schema,)
    ).fetchall()
    sequence_states = conn.execute(
        """
        SELECT sequencename, start_value, min_value, max_value, increment_by,
               cycle, cache_size, last_value
        FROM pg_sequences WHERE schemaname=%s
        ORDER BY sequencename
        """, (schema,)
    ).fetchall()
    sequence_owners = conn.execute(
        """
        SELECT seq.relname, tbl.relname, att.attname
        FROM pg_class seq
        JOIN pg_namespace sn ON sn.oid=seq.relnamespace
        JOIN pg_depend d ON d.objid=seq.oid
          AND d.classid='pg_class'::regclass
          AND d.refclassid='pg_class'::regclass
          AND d.deptype IN ('a','i')
        JOIN pg_class tbl ON tbl.oid=d.refobjid
        JOIN pg_namespace tn ON tn.oid=tbl.relnamespace
        JOIN pg_attribute att ON att.attrelid=tbl.oid AND att.attnum=d.refobjsubid
        WHERE sn.nspname=%s AND tn.nspname=%s AND seq.relkind='S'
        ORDER BY seq.relname
        """, (schema, schema)
    ).fetchall()
    return {
        "tables": {row[0]: set() for row in tables},
        "columns": {(row[0], row[1]) for row in columns},
        "column_details": [
            {"table": row[0], "column": row[1], "type": row[2], "nullable": row[3], "default": row[4]}
            for row in columns
        ],
        "indexes": {row[0] for row in indexes},
        "index_details": {
            row[0]: {
                "table": row[1], "unique": bool(row[2]), "partial": bool(row[3]),
                "expression": bool(row[4]), "method": row[5], "key_count": int(row[6]),
                "expression_sql": _normalize_index_sql(row[7]),
                "predicate_sql": _normalize_index_sql(row[8]),
            }
            for row in index_details
        },
        "sequences": {row[0] for row in sequences},
        "functions": {row[0] for row in functions},
        "function_signatures": {(row[0], tuple(_normalize_type(arg) for arg in _split_top_level(row[1]) if arg.strip())) for row in functions},
        "function_body_sha256": {
            (row[0], tuple(_normalize_type(arg) for arg in _split_top_level(row[1]) if arg.strip())):
                hashlib.sha256(str(row[2]).strip().encode("utf-8")).hexdigest()
            for row in functions
        },
        "constraints": [
            {"table": row[0], "name": row[1], "type": row[2], "definition": row[3]}
            for row in constraints
        ],
        "constraint_signatures": {
            (
                row[0], row[2], tuple(row[4] or ()) if row[2] != "c" else (),
                row[5].lower() if row[5] else None, tuple(row[6] or ()),
                _normalize_check_expression(str(row[7])) if row[2] == "c" and row[7] is not None else None,
            )
            for row in constraints
        },
        "rules": [
            {"table": row[0], "name": row[1], "definition": row[2],
             "event": row[3], "condition": row[4]}
            for row in rules
        ],
        "triggers": [
            {"table": row[0], "name": row[1], "definition": row[2]}
            for row in triggers
        ],
        "sequence_states": [
            {"name": row[0], "start": row[1], "minimum": row[2], "maximum": row[3],
             "increment": row[4], "cycle": row[5], "cache": row[6], "last_value": row[7]}
            for row in sequence_states
        ],
        "sequence_owners": {
            row[0]: {"table": row[1], "column": row[2]} for row in sequence_owners
        },
    }


def _set_diff(expected: set[str], actual: set[str]) -> dict[str, list[str]]:
    return {"missing": sorted(expected - actual), "extra": sorted(actual - expected)}


def _sequence_high_water_drift(
    conn: psycopg.Connection,
    schema: str,
    owners: dict[str, dict[str, str]],
    states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect owned sequences whose stored value is behind the owning column's maximum."""
    state_by_name = {item["name"]: item for item in states}
    drift: list[dict[str, Any]] = []
    for sequence_name, owner in owners.items():
        state = state_by_name.get(sequence_name, {})
        max_value = conn.execute(
            sql.SQL("SELECT max({}) FROM {}.{}").format(
                sql.Identifier(owner["column"]),
                sql.Identifier(schema),
                sql.Identifier(owner["table"]),
            )
        ).fetchone()[0]
        last_value = state.get("last_value")
        if max_value is not None and (last_value is None or int(last_value) < int(max_value)):
            drift.append({
                "sequence": sequence_name, "table": owner["table"], "column": owner["column"],
                "max_column_value": int(max_value),
                "last_value": int(last_value) if last_value is not None else None,
            })
    return drift


def run_preflight(archive_path: str, dsn: str, schema: str = "public") -> dict[str, Any]:
    digest = hashlib.sha256(Path(archive_path).read_bytes()).hexdigest()
    if digest != CANONICAL_A124_SHA256:
        raise ValueError(
            f"Archive SHA-256 mismatch: expected {CANONICAL_A124_SHA256}, got {digest}"
        )
    with tarfile.open(archive_path, "r:bz2") as archive:
        contents: dict[str, str] = {}
        for filename in _REQUIRED_FILES:
            try:
                member = archive.getmember(filename)
            except KeyError as exc:
                raise ValueError(f"Canonical archive is missing {filename}") from exc
            if not member.isfile():
                raise ValueError(f"Canonical archive member is not a regular file: {filename}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"Cannot read archive member {filename}")
            contents[filename] = stream.read().decode("utf-8")

    source = source_inventory(
        contents["IBSng/db/tables.sql"],
        contents["IBSng/db/functions.sql"],
        contents["IBSng/db/initial.sql"],
    )
    expected_defs = _defs_expected(contents["IBSng/db/defs.sql"])
    expected_states = _initial_state_expectations(contents["IBSng/db/initial.sql"])
    expected_admin_seed = _initial_admin_seed(
        contents["IBSng/db/initial.sql"], contents["IBSng/db/tables.sql"]
    )
    expected_god_seed = _initial_god_permission_seed(contents["IBSng/db/initial.sql"])
    with psycopg.connect(dsn) as conn:
        target = _target_inventory(conn, schema)
        source_table_names = set(source["tables"])
        target_table_names = set(target["tables"])
        source_columns = {(table, col) for table, cols in source["tables"].items() for col in cols}
        target_columns = target["columns"]
        target_details = {(row["table"], row["column"]): row for row in target["column_details"]}
        column_definition_drift: list[dict[str, Any]] = []
        for key, spec in source["column_specs"].items():
            target_row = target_details.get(key)
            if target_row is None:
                continue
            target_type = re.sub(r"\s+", " ", str(target_row["type"]).lower())
            if target_type != spec["type"]:
                column_definition_drift.append({"table": key[0], "column": key[1], "field": "type", "source": spec["type"], "target": target_type})
            if bool(target_row["nullable"]) != bool(spec["nullable"]):
                column_definition_drift.append({"table": key[0], "column": key[1], "field": "nullable", "source": spec["nullable"], "target": bool(target_row["nullable"])})
            if not spec["serial"] and _normalize_default(
                str(target_row["default"]) if target_row["default"] is not None else None
            ) != spec["default"]:
                column_definition_drift.append({
                    "table": key[0], "column": key[1], "field": "default",
                    "source": spec["default"],
                    "target": _normalize_default(str(target_row["default"]) if target_row["default"] is not None else None),
                })
        source_indexes, target_indexes = set(source["indexes"]), target["indexes"]
        source_index_details, target_index_details = source["index_details"], target["index_details"]
        index_definition_drift = [
            {
                "name": name,
                "source": source_index_details[name],
                "target": target_index_details.get(name),
            }
            for name in sorted(set(source_index_details) & set(target_index_details))
            if source_index_details[name] != target_index_details[name]
        ]
        source_sequences, target_sequences = set(source["sequences"]), target["sequences"]
        source_functions, target_functions = set(source["functions"]), target["functions"]
        source_function_signatures, target_function_signatures = source["function_signatures"], target["function_signatures"]
        source_function_bodies, target_function_bodies = source["function_body_sha256"], target["function_body_sha256"]
        function_body_drift = [
            {
                "function": name, "arguments": list(args),
                "source_sha256": source_function_bodies[(name, args)],
                "target_sha256": target_function_bodies.get((name, args)),
            }
            for name, args in sorted(source_function_bodies)
            if (name, args) in target_function_signatures
            and source_function_bodies[(name, args)] != target_function_bodies.get((name, args))
        ]
        source_sequence_owners, target_sequence_owners = source["sequence_owners"], target["sequence_owners"]
        sequence_owner_drift = []
        for sequence_name, expected_owner in source_sequence_owners.items():
            actual_owner = target_sequence_owners.get(sequence_name)
            if actual_owner != expected_owner:
                sequence_owner_drift.append({
                    "sequence": sequence_name, "source": expected_owner, "target": actual_owner,
                })
        sequence_value_drift = _sequence_high_water_drift(
            conn, schema, target_sequence_owners, target["sequence_states"]
        )
        source_constraints, target_constraints = source["constraint_signatures"], target["constraint_signatures"]
        constraint_signature_drift = {
            "missing": sorted(repr(item) for item in source_constraints - target_constraints),
            "extra": sorted(repr(item) for item in target_constraints - source_constraints),
        }
        source_rules = source["rules"]
        target_rules = {
            item["name"]: item for item in target["rules"]
            if item["name"] in source_rules
        }
        rule_drift: list[dict[str, Any]] = []
        for name, expected in source_rules.items():
            actual = target_rules.get(name)
            if actual is None:
                rule_drift.append({"name": name, "field": "presence", "source": expected, "target": None})
                continue
            observed = {
                "event": actual["event"],
                "table": actual["table"],
                "condition": _normalize_rule_condition(str(actual["condition"] or "")),
            }
            for field in ("event", "table", "condition"):
                if observed[field] != expected[field]:
                    rule_drift.append({
                        "name": name, "field": field,
                        "source": expected[field], "target": observed[field],
                    })
        required_data_tables = {"defs", "admins", "admin_perms", "ibs_states"}
        present_data_tables = set()
        for table_name in required_data_tables:
            exists = conn.execute(
                """
                SELECT EXISTS (
                  SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                  WHERE n.nspname=%s AND c.relname=%s AND c.relkind IN ('r','p')
                )
                """, (schema, table_name)
            ).fetchone()[0]
            if exists:
                present_data_tables.add(table_name)
        if "defs" in present_data_tables:
            defs_table = sql.Identifier(schema, "defs")
            actual_defs_rows = conn.execute(
                sql.SQL("SELECT name, value FROM {} WHERE name = ANY(%s)").format(defs_table),
                (list(expected_defs),),
            ).fetchall()
            actual_defs = dict(actual_defs_rows)
        else:
            actual_defs = {}
        missing_defs = sorted(set(expected_defs) - set(actual_defs))
        wrong_defs = sorted(name for name in set(expected_defs) & set(actual_defs) if expected_defs[name] != actual_defs[name])
        if "ibs_states" in target["tables"]:
            actual_state_rows = conn.execute(
                sql.SQL("SELECT name, value FROM {} WHERE name = ANY(%s)").format(
                    sql.Identifier(schema, "ibs_states")
                ),
                (list(expected_states),),
            ).fetchall()
            actual_states = dict(actual_state_rows)
        else:
            actual_states = {}
        missing_states = sorted(set(expected_states) - set(actual_states))
        wrong_states = sorted(
            name for name in set(expected_states) & set(actual_states)
            if expected_states[name] != actual_states[name]
        )
        admin_columns = list(expected_admin_seed)
        admin_row = conn.execute(
            sql.SQL("SELECT {} FROM {} WHERE admin_id=0").format(
                sql.SQL(", ").join(sql.Identifier(column) for column in admin_columns),
                sql.Identifier(schema, "admins"),
            )
        ).fetchone() if "admins" in target["tables"] else None
        actual_admin_seed = dict(zip(admin_columns, admin_row, strict=True)) if admin_row is not None else {}
        admin_seed_drift = sorted(
            column for column, expected in expected_admin_seed.items()
            if column not in actual_admin_seed
            or not _seed_values_equal(
                expected, actual_admin_seed[column], source["column_specs"].get(("admins", column))
            )
        )
        god_columns = list(expected_god_seed)
        god_row = conn.execute(
            sql.SQL("SELECT {} FROM {} WHERE admin_id=0 AND perm_name='GOD'").format(
                sql.SQL(", ").join(sql.Identifier(column) for column in god_columns),
                sql.Identifier(schema, "admin_perms"),
            )
        ).fetchone() if "admin_perms" in target["tables"] else None
        actual_god_seed = dict(zip(god_columns, god_row, strict=True)) if god_row is not None else {}
        god_seed_drift = sorted(
            column for column, expected in expected_god_seed.items()
            if column not in actual_god_seed or actual_god_seed[column] != expected
        )
        marker_queries = {
            "system_admin": ("admins", "SELECT EXISTS (SELECT 1 FROM {} WHERE admin_id=0 AND username='system')"),
            "system_god_permission": ("admin_perms", "SELECT EXISTS (SELECT 1 FROM {} WHERE admin_id=0 AND perm_name='GOD')"),
            "midnight_jobs_state": ("ibs_states", "SELECT EXISTS (SELECT 1 FROM {} WHERE name='MIDNIGHT_JOBS' AND value='0')"),
            "lowload_jobs_state": ("ibs_states", "SELECT EXISTS (SELECT 1 FROM {} WHERE name='LOWLOAD_JOBS' AND value='0')"),
        }
        seed_markers: dict[str, bool] = {}
        for marker, (table_name, query) in marker_queries.items():
            if table_name not in present_data_tables:
                seed_markers[marker] = False
            else:
                seed_markers[marker] = bool(conn.execute(
                    sql.SQL(query).format(sql.Identifier(schema, table_name))
                ).fetchone()[0])
        present_rules = {
            row[0] for row in conn.execute(
                """
                SELECT r.rulename
                FROM pg_rewrite r
                JOIN pg_class c ON c.oid=r.ev_class
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=%s AND r.rulename IN ('system_admin','system_admin_god')
                """, (schema,)
            ).fetchall()
        }
        seed_markers["system_admin_delete_rule"] = "system_admin" in present_rules
        seed_markers["system_god_delete_rule"] = "system_admin_god" in present_rules
    report = {
        "source_archive_sha256": digest,
        "target_schema": schema,
        "inventory": {
            "tables": {"missing": sorted(source_table_names - target_table_names), "extra": sorted(target_table_names - source_table_names)},
            "columns": {"missing": sorted(f"{t}.{c}" for t, c in source_columns - target_columns),
                        "extra": sorted(f"{t}.{c}" for t, c in target_columns - source_columns)},
            "explicit_indexes": _set_diff(source_indexes, target_indexes),
            "index_definition_drift": index_definition_drift,
            "sequences": _set_diff(source_sequences, target_sequences),
            "function_names": _set_diff(source_functions, target_functions),
            "function_signatures": {
                "missing": sorted(f"{name}({', '.join(args)})" for name, args in source_function_signatures - target_function_signatures),
                "extra": sorted(f"{name}({', '.join(args)})" for name, args in target_function_signatures - source_function_signatures),
            },
            "function_body_drift": function_body_drift,
            "sequence_owner_drift": sequence_owner_drift,
            "sequence_value_drift": sequence_value_drift,
            "column_definition_drift": column_definition_drift,
            "constraint_signature_drift": constraint_signature_drift,
            "source_defined_protection_rules": {
                "missing": sorted(set(source_rules) - set(target_rules)),
                "extra": sorted(set(item["name"] for item in target["rules"]) - set(source_rules)),
                "definition_drift": rule_drift,
            },
        },
        "target_semantic_objects": {
            "constraints": target["constraints"],
            "rules": target["rules"],
            "triggers": target["triggers"],
            "sequence_states": target["sequence_states"],
            "sequence_owners": target["sequence_owners"],
            "note": (
                "Read-only target-side evidence for review; these objects are inventoried "
                "but are not yet semantically compared with canonical A1.24 definitions."
            ),
        },
        "native_data": {
            "definition_count_expected": len(expected_defs),
            "definition_count_found": len(actual_defs),
            "missing_definitions": missing_defs,
            "definitions_with_value_drift": wrong_defs,
            "initial_state_count_expected": len(expected_states),
            "initial_state_count_found": len(actual_states),
            "missing_initial_states": missing_states,
            "initial_states_with_value_drift": wrong_states,
            "system_admin_seed_fields_with_drift": admin_seed_drift,
            "system_god_permission_seed_fields_with_drift": god_seed_drift,
            "required_seed_markers": seed_markers,
        },
        "scope": (
            "Read-only readiness evidence only. Compares source-derived PK/UNIQUE/FK/CHECK signatures, but not every index definition or trigger body; plugin objects, all data, "
            "manually advanced/unowned sequence values, backup/restore fidelity, and runtime behavior remain outside scope. A clean result "
            "does not authorize migration-ledger stamping or production cutover."
        ),
    }
    inv = report["inventory"]
    data = report["native_data"]
    report["passes_audited_checks"] = (
        not any(inv[key]["missing"] or inv[key]["extra"] for key in ("tables", "columns", "explicit_indexes", "sequences", "function_names", "function_signatures"))
        and not inv["function_body_drift"]
        and not inv["sequence_owner_drift"]
        and not inv["sequence_value_drift"]
        and not inv["index_definition_drift"]
        and not data["missing_definitions"]
        and not data["definitions_with_value_drift"]
        and not data["missing_initial_states"]
        and not data["initial_states_with_value_drift"]
        and not data["system_admin_seed_fields_with_drift"]
        and not data["system_god_permission_seed_fields_with_drift"]
        and not inv["column_definition_drift"]
        and not inv["constraint_signature_drift"]["missing"]
        and not inv["constraint_signature_drift"]["extra"]
        and not inv["source_defined_protection_rules"]["missing"]
        and not inv["source_defined_protection_rules"]["extra"]
        and not inv["source_defined_protection_rules"]["definition_drift"]
        and all(data["required_seed_markers"].values())
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="Canonical IBSng-A1.24.tar.bz2")
    parser.add_argument("--dsn", required=True, help="Target PostgreSQL DSN")
    parser.add_argument("--schema", default="public")
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument("--fail-on-drift", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_preflight(args.archive, args.dsn, args.schema)
    except Exception as exc:
        print(f"A1.24 adoption preflight failed: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 1 if args.fail_on_drift and not report["passes_audited_checks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
