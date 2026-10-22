"""Read-only schema inventory audit against IBSng A1.24 static DDL."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from typing import Iterable, Mapping

_CREATE_TABLE = re.compile(
    r'\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?(?:"?([\w]+)"?)\s*\(', re.I
)
_CREATE_INDEX = re.compile(
    r'\bcreate\s+(?:unique\s+)?index\s+(?:"?([\w]+)"?)\s+on\s+(?:"?([\w]+)"?)\b', re.I
)
_CREATE_SEQUENCE = re.compile(r'\bcreate\s+sequence\s+(?:"?([\w]+)"?)\b', re.I)
_CONSTRAINT = re.compile(
    r'^(?:constraint\s+\S+\s+)?(?:primary\s+key|foreign\s+key|unique|check|exclude)\b', re.I
)


def _split(body: str) -> list[str]:
    """Split a SQL list on top-level commas, preserving quoted strings and nested types."""
    parts, start, depth, quote, i = [], 0, 0, None, 0
    while i < len(body):
        ch = body[i]
        if quote:
            if ch == quote:
                if i + 1 < len(body) and body[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(body[start:i].strip())
            start = i + 1
        i += 1
    if body[start:].strip():
        parts.append(body[start:].strip())
    return parts


def _clean_sql(sql: str) -> str:
    """Remove SQL line comments without deleting comment markers inside quoted strings."""
    out, quote, i = [], None, 0
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
        elif ch in ("'", '"'):
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


def _table_bodies(sql: str) -> Iterable[tuple[str, str]]:
    for match in _CREATE_TABLE.finditer(sql):
        depth, quote, i, start = 1, None, match.end(), match.end()
        while i < len(sql) and depth:
            ch = sql[i]
            if quote:
                if ch == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote:
                        i += 1
                    else:
                        quote = None
            elif ch in ("'", '"'):
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        if depth:
            raise ValueError(f"Unterminated CREATE TABLE for {match.group(1)}")
        yield match.group(1).lower(), sql[start:i - 1]


def parse_a124_tables(sql: str) -> dict[str, dict[str, str]]:
    """Parse table/column declarations from IBSng/db/tables.sql; fail closed on ambiguity."""
    cleaned = _clean_sql(sql)
    tables: dict[str, dict[str, str]] = {}
    for table, body in _table_bodies(cleaned):
        if table in tables:
            raise ValueError(f"Duplicate table {table}")
        columns: dict[str, str] = {}
        for declaration in _split(body):
            if not declaration or _CONSTRAINT.match(declaration):
                continue
            col = re.match(r'^(?:"([^"]+)"|([A-Za-z_][\w$]*))\s+(.+)$', declaration, re.S)
            if not col:
                raise ValueError(f"Cannot parse column in {table}: {declaration!r}")
            name = (col.group(1) or col.group(2)).lower()
            if name in columns:
                raise ValueError(f"Duplicate column {table}.{name}")
            columns[name] = " ".join(col.group(3).split())
        tables[table] = columns
    if not tables:
        raise ValueError("No CREATE TABLE statements found in A1.24 tables.sql")
    return tables


def parse_a124_inventory(sql: str) -> dict[str, object]:
    """Parse static tables, explicit indexes and sequences plus serial-owned sequences."""
    cleaned = _clean_sql(sql)
    tables = parse_a124_tables(cleaned)
    indexes = sorted({m.group(1).lower() for m in _CREATE_INDEX.finditer(cleaned)})
    sequences = {m.group(1).lower() for m in _CREATE_SEQUENCE.finditer(cleaned)}
    for table, columns in tables.items():
        for column, declaration in columns.items():
            if re.match(r'^(?:smallserial|serial|bigserial)\b', declaration, re.I):
                sequences.add(f"{table}_{column}_seq")
    return {
        "tables": tables,
        "indexes": indexes,
        "sequences": sorted(sequences),
    }


def read_a124_schema(archive_path: str) -> tuple[str, dict[str, object]]:
    digest = hashlib.sha256()
    with open(archive_path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    with tarfile.open(archive_path, "r:bz2") as archive:
        try:
            member = archive.getmember("IBSng/db/tables.sql")
        except KeyError as exc:
            raise ValueError("Archive is missing IBSng/db/tables.sql") from exc
        if not member.isfile():
            raise ValueError("IBSng/db/tables.sql is not a regular file")
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("Cannot read IBSng/db/tables.sql")
        sql = source.read().decode("utf-8", errors="strict")
    return digest.hexdigest(), parse_a124_inventory(sql)


def compare_schema(
    source: Mapping[str, Mapping[str, str]], target_columns: Iterable[tuple[str, str]]
) -> dict[str, object]:
    """Backward-compatible table/column name comparison."""
    src = {t.lower(): {c.lower() for c in cols} for t, cols in source.items()}
    target: dict[str, set[str]] = {}
    for table, column in target_columns:
        target.setdefault(table.lower(), set()).add(column.lower())
    shared = set(src) & set(target)
    missing_tables, extra_tables = sorted(set(src) - set(target)), sorted(set(target) - set(src))
    missing_columns = {t: sorted(src[t] - target[t]) for t in sorted(shared) if src[t] - target[t]}
    extra_columns = {t: sorted(target[t] - src[t]) for t in sorted(shared) if target[t] - src[t]}
    drift = (
        len(missing_tables) + len(extra_tables)
        + sum(map(len, missing_columns.values())) + sum(map(len, extra_columns.values()))
    )
    return {
        "source_table_count": len(src), "target_table_count": len(target),
        "missing_tables": missing_tables, "extra_tables": extra_tables,
        "missing_columns": missing_columns, "extra_columns": extra_columns,
        "drift_count": drift, "matches_by_name": drift == 0,
    }


def compare_inventory(source: Mapping[str, object], target: Mapping[str, object]) -> dict[str, object]:
    """Compare A1.24 table/column names and explicit index/sequence names."""
    table_report = compare_schema(
        source["tables"],  # type: ignore[arg-type]
        target["columns"],  # type: ignore[arg-type]
    )
    source_indexes, target_indexes = set(source["indexes"]), set(target["indexes"])  # type: ignore[arg-type]
    source_sequences, target_sequences = set(source["sequences"]), set(target["sequences"])  # type: ignore[arg-type]
    missing_indexes = sorted(source_indexes - target_indexes)
    extra_indexes = sorted(target_indexes - source_indexes)
    missing_sequences = sorted(source_sequences - target_sequences)
    extra_sequences = sorted(target_sequences - source_sequences)
    inventory_drift = (
        table_report["drift_count"] + len(missing_indexes) + len(extra_indexes)
        + len(missing_sequences) + len(extra_sequences)
    )
    return {
        **table_report,
        "source_index_count": len(source_indexes),
        "target_index_count": len(target_indexes),
        "missing_indexes": missing_indexes,
        "extra_indexes": extra_indexes,
        "source_sequence_count": len(source_sequences),
        "target_sequence_count": len(target_sequences),
        "missing_sequences": missing_sequences,
        "extra_sequences": extra_sequences,
        "inventory_drift_count": inventory_drift,
        "matches_inventory_by_name": inventory_drift == 0,
        "scope_note": (
            "Name-level comparison of static IBSng/db/tables.sql objects. Does not compare "
            "column types/defaults/nullability, constraints, extension/plugin DDL, functions, "
            "data, backup/restore fidelity, or runtime behavior. Constraint-backed indexes "
            "are excluded from the target explicit-index inventory."
        ),
    }


def _target_inventory(dsn: str, schema: str) -> dict[str, object]:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required to query the target PostgreSQL schema") from exc
    with psycopg.connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_class.relname, attribute.attname
            FROM pg_class AS table_class
            JOIN pg_namespace AS namespace ON namespace.oid = table_class.relnamespace
            JOIN pg_attribute AS attribute ON attribute.attrelid = table_class.oid
            WHERE namespace.nspname = %s
              AND table_class.relkind IN ('r', 'p')
              AND attribute.attnum > 0
              AND NOT attribute.attisdropped
            ORDER BY table_class.relname, attribute.attnum
            """, (schema,)
        )
        columns = [(str(table), str(column)) for table, column in cursor.fetchall()]
        cursor.execute(
            """
            SELECT index_class.relname
            FROM pg_class AS table_class
            JOIN pg_namespace AS namespace ON namespace.oid = table_class.relnamespace
            JOIN pg_index AS indexes ON indexes.indrelid = table_class.oid
            JOIN pg_class AS index_class ON index_class.oid = indexes.indexrelid
            LEFT JOIN pg_constraint AS constraints ON constraints.conindid = indexes.indexrelid
            WHERE namespace.nspname = %s AND table_class.relkind IN ('r', 'p')
              AND constraints.oid IS NULL
            ORDER BY index_class.relname
            """, (schema,)
        )
        indexes = [str(row[0]) for row in cursor.fetchall()]
        cursor.execute(
            "SELECT sequencename FROM pg_sequences WHERE schemaname = %s ORDER BY sequencename",
            (schema,)
        )
        sequences = [str(row[0]) for row in cursor.fetchall()]
    return {"columns": columns, "indexes": indexes, "sequences": sequences}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="Canonical IBSng-A1.24.tar.bz2")
    parser.add_argument("--dsn", required=True, help="Target PostgreSQL DSN")
    parser.add_argument("--schema", default="public")
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument("--fail-on-drift", action="store_true")
    args = parser.parse_args(argv)
    try:
        digest, source = read_a124_schema(args.archive)
        target = _target_inventory(args.dsn, args.schema)
        report = {
            "source": "IBSng A1.24",
            "archive_sha256": digest,
            "source_schema_file": "IBSng/db/tables.sql",
            "target_schema": args.schema,
            "comparison": compare_inventory(source, target),
        }
    except Exception as exc:
        print(f"schema parity audit failed: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream:
            stream.write(rendered)
    else:
        sys.stdout.write(rendered)
    return 2 if args.fail_on_drift and not report["comparison"]["matches_inventory_by_name"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
