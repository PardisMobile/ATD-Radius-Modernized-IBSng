"""Read-only name-level schema audit against IBSng A1.24 static DDL."""
from __future__ import annotations
import argparse, hashlib, json, re, sys, tarfile
from typing import Iterable, Mapping

_CREATE_TABLE = re.compile(r'\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?(?:"?([\w]+)"?)\s*\(', re.I)
_CONSTRAINT = re.compile(r'^(?:constraint\s+\S+\s+)?(?:primary\s+key|foreign\s+key|unique|check|exclude)\b', re.I)


def _split(body: str) -> list[str]:
    parts, start, depth, quote, i = [], 0, 0, None, 0
    while i < len(body):
        ch = body[i]
        if quote:
            if ch == quote:
                if i + 1 < len(body) and body[i + 1] == quote: i += 1
                else: quote = None
        elif ch in ("'", '"'): quote = ch
        elif ch == "(": depth += 1
        elif ch == ")": depth -= 1
        elif ch == "," and depth == 0:
            parts.append(body[start:i].strip()); start = i + 1
        i += 1
    if body[start:].strip(): parts.append(body[start:].strip())
    return parts


def parse_a124_tables(sql: str) -> dict[str, dict[str, str]]:
    """Parse table/column names from IBSng/db/tables.sql; fail closed on ambiguity."""
    cleaned = re.sub(r'--[^\n]*', '', sql)
    tables: dict[str, dict[str, str]] = {}
    for match in _CREATE_TABLE.finditer(cleaned):
        depth, quote, i, start = 1, None, match.end(), match.end()
        while i < len(cleaned) and depth:
            ch = cleaned[i]
            if quote:
                if ch == quote:
                    if i + 1 < len(cleaned) and cleaned[i + 1] == quote: i += 1
                    else: quote = None
            elif ch in ("'", '"'): quote = ch
            elif ch == "(": depth += 1
            elif ch == ")": depth -= 1
            i += 1
        if depth: raise ValueError(f"Unterminated CREATE TABLE for {match.group(1)}")
        table = match.group(1).lower()
        if table in tables: raise ValueError(f"Duplicate table {table}")
        columns: dict[str, str] = {}
        for declaration in _split(cleaned[start:i - 1]):
            if not declaration or _CONSTRAINT.match(declaration): continue
            col = re.match(r'^(?:"([^"]+)"|([A-Za-z_][\w$]*))\s+(.+)$', declaration, re.S)
            if not col: raise ValueError(f"Cannot parse column in {table}: {declaration!r}")
            name = (col.group(1) or col.group(2)).lower()
            if name in columns: raise ValueError(f"Duplicate column {table}.{name}")
            columns[name] = " ".join(col.group(3).split())
        tables[table] = columns
    if not tables: raise ValueError("No CREATE TABLE statements found in A1.24 tables.sql")
    return tables


def read_a124_schema(archive_path: str) -> tuple[str, dict[str, dict[str, str]]]:
    digest = hashlib.sha256()
    with open(archive_path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    with tarfile.open(archive_path, "r:bz2") as archive:
        try: member = archive.getmember("IBSng/db/tables.sql")
        except KeyError as exc: raise ValueError("Archive is missing IBSng/db/tables.sql") from exc
        if not member.isfile(): raise ValueError("IBSng/db/tables.sql is not a regular file")
        source = archive.extractfile(member)
        if source is None: raise ValueError("Cannot read IBSng/db/tables.sql")
        sql = source.read().decode("utf-8", errors="strict")
    return digest.hexdigest(), parse_a124_tables(sql)


def compare_schema(source: Mapping[str, Mapping[str, str]], target_columns: Iterable[tuple[str, str]]) -> dict[str, object]:
    src = {t.lower(): {c.lower() for c in cols} for t, cols in source.items()}
    target: dict[str, set[str]] = {}
    for table, column in target_columns: target.setdefault(table.lower(), set()).add(column.lower())
    shared = set(src) & set(target)
    missing_tables, extra_tables = sorted(set(src) - set(target)), sorted(set(target) - set(src))
    missing_columns = {t: sorted(src[t] - target[t]) for t in sorted(shared) if src[t] - target[t]}
    extra_columns = {t: sorted(target[t] - src[t]) for t in sorted(shared) if target[t] - src[t]}
    drift = len(missing_tables) + len(extra_tables) + sum(map(len, missing_columns.values())) + sum(map(len, extra_columns.values()))
    return {
        "source_table_count": len(src), "target_table_count": len(target),
        "missing_tables": missing_tables, "extra_tables": extra_tables,
        "missing_columns": missing_columns, "extra_columns": extra_columns,
        "drift_count": drift, "matches_by_name": drift == 0,
        "scope_note": "Name-level comparison of IBSng/db/tables.sql only; excludes types/defaults/constraints/indexes/sequences, plugin-created tables, functions, data, restore fidelity, and runtime behavior.",
    }


def _target_columns(dsn: str, schema: str) -> list[tuple[str, str]]:
    try: import psycopg
    except ImportError as exc: raise RuntimeError("psycopg is required to query the target PostgreSQL schema") from exc
    with psycopg.connect(dsn) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = %s ORDER BY table_name, ordinal_position", (schema,))
        return [(str(t), str(c)) for t, c in cursor.fetchall()]


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
        report = {"source": "IBSng A1.24", "archive_sha256": digest, "source_schema_file": "IBSng/db/tables.sql",
                  "target_schema": args.schema, "comparison": compare_schema(source, _target_columns(args.dsn, args.schema))}
    except Exception as exc:
        print(f"schema parity audit failed: {exc}", file=sys.stderr); return 1
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as stream: stream.write(rendered)
    else: sys.stdout.write(rendered)
    return 2 if args.fail_on_drift and not report["comparison"]["matches_by_name"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
