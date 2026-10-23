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

def source_inventory(tables_sql: str, functions_sql: str) -> dict[str, Any]:
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
            match = re.match(r'^"?([a-z_][\w$]*)"?\s+(.+)


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
    sequences = conn.execute(
        "SELECT sequencename FROM pg_sequences WHERE schemaname=%s", (schema,)
    ).fetchall()
    functions = conn.execute(
        """
        SELECT DISTINCT p.proname
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname=%s
        """, (schema,)
    ).fetchall()
    return {
        "tables": {row[0]: set() for row in tables},
        "columns": {(table, column) for table, column in columns},
        "indexes": {row[0] for row in indexes},
        "sequences": {row[0] for row in sequences},
        "functions": {row[0] for row in functions},
    }


def _set_diff(expected: set[str], actual: set[str]) -> dict[str, list[str]]:
    return {"missing": sorted(expected - actual), "extra": sorted(actual - expected)}


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

    source = source_inventory(contents["IBSng/db/tables.sql"], contents["IBSng/db/functions.sql"])
    expected_defs = _defs_expected(contents["IBSng/db/defs.sql"])
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
        source_sequences, target_sequences = set(source["sequences"]), target["sequences"]
        source_functions, target_functions = set(source["functions"]), target["functions"]
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
            "sequences": _set_diff(source_sequences, target_sequences),
            "function_names": _set_diff(source_functions, target_functions),
            "column_definition_drift": column_definition_drift,
        },
        "native_data": {
            "definition_count_expected": len(expected_defs),
            "definition_count_found": len(actual_defs),
            "missing_definitions": missing_defs,
            "definitions_with_value_drift": wrong_defs,
            "required_seed_markers": seed_markers,
        },
        "scope": (
            "Read-only readiness evidence only. Does not compare every column type/default, "
            "constraint or rule definition, function body/signature, plugin object, all data, "
            "sequence values, backup/restore fidelity, or runtime behavior. A clean result "
            "does not authorize migration-ledger stamping or production cutover."
        ),
    }
    inv = report["inventory"]
    data = report["native_data"]
    report["passes_audited_checks"] = (
        not any(inv[key]["missing"] or inv[key]["extra"] for key in ("tables", "columns", "explicit_indexes", "sequences", "function_names"))
        and not data["missing_definitions"]
        and not data["definitions_with_value_drift"]
        and not inv["column_definition_drift"]
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
, declaration, re.I | re.S)
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
    functions = {m.group(1).lower() for m in _CREATE_FUNCTION.finditer(_strip_line_comments(functions_sql))}
    if not functions:
        raise ValueError("No functions found in canonical A1.24 functions.sql")
    return {"tables": tables, "column_specs": column_specs, "indexes": indexes, "sequences": sequences, "functions": functions}


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
        SELECT c.relname, a.attname
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid
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
    sequences = conn.execute(
        "SELECT sequencename FROM pg_sequences WHERE schemaname=%s", (schema,)
    ).fetchall()
    functions = conn.execute(
        """
        SELECT DISTINCT p.proname
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname=%s
        """, (schema,)
    ).fetchall()
    return {
        "tables": {row[0]: set() for row in tables},
        "columns": {(table, column) for table, column in columns},
        "indexes": {row[0] for row in indexes},
        "sequences": {row[0] for row in sequences},
        "functions": {row[0] for row in functions},
    }


def _set_diff(expected: set[str], actual: set[str]) -> dict[str, list[str]]:
    return {"missing": sorted(expected - actual), "extra": sorted(actual - expected)}


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

    source = source_inventory(contents["IBSng/db/tables.sql"], contents["IBSng/db/functions.sql"])
    expected_defs = _defs_expected(contents["IBSng/db/defs.sql"])
    with psycopg.connect(dsn) as conn:
        target = _target_inventory(conn, schema)
        source_table_names = set(source["tables"])
        target_table_names = set(target["tables"])
        source_columns = {(table, col) for table, cols in source["tables"].items() for col in cols}
        target_columns = target["columns"]
        source_indexes, target_indexes = set(source["indexes"]), target["indexes"]
        source_sequences, target_sequences = set(source["sequences"]), target["sequences"]
        source_functions, target_functions = set(source["functions"]), target["functions"]
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
            "sequences": _set_diff(source_sequences, target_sequences),
            "function_names": _set_diff(source_functions, target_functions),
        },
        "native_data": {
            "definition_count_expected": len(expected_defs),
            "definition_count_found": len(actual_defs),
            "missing_definitions": missing_defs,
            "definitions_with_value_drift": wrong_defs,
            "required_seed_markers": seed_markers,
        },
        "scope": (
            "Read-only readiness evidence only. Does not compare every column type/default, "
            "constraint or rule definition, function body/signature, plugin object, all data, "
            "sequence values, backup/restore fidelity, or runtime behavior. A clean result "
            "does not authorize migration-ledger stamping or production cutover."
        ),
    }
    inv = report["inventory"]
    data = report["native_data"]
    report["passes_audited_checks"] = (
        not any(inv[key]["missing"] or inv[key]["extra"] for key in ("tables", "columns", "explicit_indexes", "sequences", "function_names"))
        and not data["missing_definitions"]
        and not data["definitions_with_value_drift"]
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
