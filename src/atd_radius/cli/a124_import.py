"""Fail-closed, transactional A1.24 row import into an existing ATD schema.

This tool transfers data only. It never creates/drops tables and never imports
legacy functions, triggers, rules, or plugin DDL. Every source table must have
an exact target table/column shape and a stable unique key; otherwise it refuses
to proceed rather than silently omit or flatten data.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from atd_radius.compatibility.a124_schema_parity import parse_a124_inventory, read_a124_schema

CANONICAL_A124_SHA256 = "c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8"


class A124ImportError(RuntimeError):
    """Raised when an A1.24 data import cannot be proven safe."""


def _tables(conn, schema: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema=%s AND table_type='BASE TABLE'
        ORDER BY table_name
        """, (schema,)
    ).fetchall()
    return [str(row[0]) for row in rows]


def _columns(conn, schema: str, table: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT attribute.attname,
               pg_catalog.format_type(attribute.atttypid, attribute.atttypmod),
               NOT attribute.attnotnull,
               attribute.attgenerated,
               attribute.attidentity
        FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid=relation.relnamespace
        JOIN pg_attribute AS attribute ON attribute.attrelid=relation.oid
        WHERE namespace.nspname=%s AND relation.relname=%s
          AND relation.relkind IN ('r', 'p')
          AND attribute.attnum > 0 AND NOT attribute.attisdropped
        ORDER BY attribute.attnum
        """, (schema, table)
    ).fetchall()
    return [
        {"name": str(name), "type": str(type_name), "nullable": bool(nullable),
         "generated": str(generated or ""), "identity": str(identity or "")}
        for name, type_name, nullable, generated, identity in rows
    ]


def _key_columns(conn, schema: str, table: str) -> tuple[str, ...]:
    rows = conn.execute(
        """
        SELECT index_class.relname, indexes.indisprimary,
               array_agg(attribute.attname ORDER BY key_column.ordinality)
        FROM pg_class AS table_class
        JOIN pg_namespace AS namespace ON namespace.oid=table_class.relnamespace
        JOIN pg_index AS indexes ON indexes.indrelid=table_class.oid
        JOIN pg_class AS index_class ON index_class.oid=indexes.indexrelid
        JOIN LATERAL unnest(indexes.indkey) WITH ORDINALITY
             AS key_column(attnum, ordinality) ON key_column.ordinality <= indexes.indnkeyatts
        JOIN pg_attribute AS attribute
          ON attribute.attrelid=table_class.oid AND attribute.attnum=key_column.attnum
        WHERE namespace.nspname=%s AND table_class.relname=%s
          AND indexes.indisunique AND indexes.indisvalid
          AND indexes.indpred IS NULL AND indexes.indexprs IS NULL
        GROUP BY index_class.relname, indexes.indisprimary, indexes.indnkeyatts
        ORDER BY indexes.indisprimary DESC, indexes.indnkeyatts, index_class.relname
        """, (schema, table)
    ).fetchall()
    if not rows:
        raise A124ImportError(
            f"table {schema}.{table} has no simple primary/unique key; safe repeatable import is impossible"
        )
    return tuple(str(col) for col in rows[0][2])


def _foreign_keys(conn, schema: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT child.relname, parent.relname,
               array_agg(child_column.attname ORDER BY child_key.ordinality),
               array_agg(parent_column.attname ORDER BY parent_key.ordinality)
        FROM pg_constraint AS constraint_row
        JOIN pg_class AS child ON child.oid=constraint_row.conrelid
        JOIN pg_namespace AS child_ns ON child_ns.oid=child.relnamespace
        JOIN pg_class AS parent ON parent.oid=constraint_row.confrelid
        JOIN pg_namespace AS parent_ns ON parent_ns.oid=parent.relnamespace
        JOIN LATERAL unnest(constraint_row.conkey) WITH ORDINALITY
             AS child_key(attnum, ordinality) ON TRUE
        JOIN pg_attribute AS child_column
          ON child_column.attrelid=child.oid AND child_column.attnum=child_key.attnum
        JOIN LATERAL unnest(constraint_row.confkey) WITH ORDINALITY
             AS parent_key(attnum, ordinality) ON parent_key.ordinality=child_key.ordinality
        JOIN pg_attribute AS parent_column
          ON parent_column.attrelid=parent.oid AND parent_column.attnum=parent_key.attnum
        WHERE constraint_row.contype='f'
          AND child_ns.nspname=%s AND parent_ns.nspname=%s
        GROUP BY child.relname, parent.relname, constraint_row.oid
        ORDER BY child.relname, parent.relname
        """, (schema, schema)
    ).fetchall()
    return [
        {"child": str(child), "parent": str(parent),
         "child_columns": tuple(str(x) for x in child_cols),
         "parent_columns": tuple(str(x) for x in parent_cols)}
        for child, parent, child_cols, parent_cols in rows
    ]


def _table_order(tables: list[str], foreign_keys: list[dict[str, Any]]) -> list[str]:
    """Order referenced tables before dependent tables; reject cross-table FK cycles."""
    dependencies: dict[str, set[str]] = {table: set() for table in tables}
    children: dict[str, set[str]] = defaultdict(set)
    for fk in foreign_keys:
        child, parent = fk["child"], fk["parent"]
        if child != parent:
            dependencies[child].add(parent)
            children[parent].add(child)
    ready = deque(sorted(table for table, deps in dependencies.items() if not deps))
    ordered: list[str] = []
    while ready:
        parent = ready.popleft()
        ordered.append(parent)
        for child in sorted(children[parent]):
            dependencies[child].discard(parent)
            if not dependencies[child]:
                ready.append(child)
    if len(ordered) != len(tables):
        cyclic = sorted(set(tables) - set(ordered))
        raise A124ImportError(
            f"cross-table foreign-key cycle cannot be safely ordered: {cyclic}; no data was imported"
        )
    return ordered


def _sequence_specs(conn, schema: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT relation.relname, sequence.seqstart, sequence.seqincrement,
               sequence.seqmin, sequence.seqmax, sequence.seqcache, sequence.seqcycle
        FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid=relation.relnamespace
        JOIN pg_sequence AS sequence ON sequence.seqrelid=relation.oid
        WHERE namespace.nspname=%s AND relation.relkind='S'
        ORDER BY relation.relname
        """, (schema,)
    ).fetchall()
    return {
        str(name): {"start": int(start), "increment": int(increment), "min": int(minimum),
                    "max": int(maximum), "cache": int(cache), "cycle": bool(cycle)}
        for name, start, increment, minimum, maximum, cache, cycle in rows
    }


def _sequence_owners(conn, schema: str) -> dict[str, tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT sequence_class.relname, table_class.relname, attribute.attname
        FROM pg_class AS sequence_class
        JOIN pg_namespace AS namespace ON namespace.oid=sequence_class.relnamespace
        JOIN pg_depend AS dependency
          ON dependency.classid='pg_class'::regclass
         AND dependency.objid=sequence_class.oid
         AND dependency.refclassid='pg_class'::regclass
         AND dependency.deptype IN ('a', 'i')
        JOIN pg_class AS table_class ON table_class.oid=dependency.refobjid
        JOIN pg_attribute AS attribute
          ON attribute.attrelid=table_class.oid AND attribute.attnum=dependency.refobjsubid
        WHERE namespace.nspname=%s AND sequence_class.relkind='S'
        ORDER BY sequence_class.relname
        """, (schema,)
    ).fetchall()
    return {str(sequence): (str(table), str(column)) for sequence, table, column in rows}


def _sequence_state(conn, schema: str, name: str) -> tuple[int, bool]:
    row = conn.execute(
        sql.SQL("SELECT last_value, is_called FROM {}.{}").format(
            sql.Identifier(schema), sql.Identifier(name)
        )
    ).fetchone()
    return int(row[0]), bool(row[1])


def _owned_column_max(conn, schema: str, table: str, column: str) -> int | None:
    value = conn.execute(
        sql.SQL("SELECT max({}) FROM {}.{}").format(
            sql.Identifier(column), sql.Identifier(schema), sql.Identifier(table)
        )
    ).fetchone()[0]
    return int(value) if value is not None else None


def _has_null_key(conn, schema: str, table: str, keys: tuple[str, ...]) -> bool:
    predicate = sql.SQL(" OR ").join(sql.SQL("{} IS NULL").format(sql.Identifier(key)) for key in keys)
    return conn.execute(
        sql.SQL("SELECT EXISTS (SELECT 1 FROM {}.{} WHERE {} LIMIT 1)").format(
            sql.Identifier(schema), sql.Identifier(table), predicate
        )
    ).fetchone()[0]


def _plan(source_conn, target_conn, source_schema: str, target_schema: str,
          canonical_tables: dict[str, dict[str, str]]) -> dict[str, Any]:
    source_tables = _tables(source_conn, source_schema)
    target_tables = set(_tables(target_conn, target_schema))
    missing_canonical = sorted(set(canonical_tables) - set(source_tables))
    if missing_canonical:
        raise A124ImportError(f"source database is missing canonical A1.24 tables: {missing_canonical}")
    missing_target = sorted(set(source_tables) - target_tables)
    if missing_target:
        raise A124ImportError(
            "target schema is missing source/plugin tables; refusing to omit their data: "
            f"{missing_target}"
        )

    table_plans: list[dict[str, Any]] = []
    for table in source_tables:
        source_columns = _columns(source_conn, source_schema, table)
        target_columns = _columns(target_conn, target_schema, table)
        source_shape = [(c["name"], c["type"], c["nullable"], c["generated"], c["identity"])
                        for c in source_columns]
        target_shape = [(c["name"], c["type"], c["nullable"], c["generated"], c["identity"])
                        for c in target_columns]
        if source_shape != target_shape:
            raise A124ImportError(
                f"schema mismatch for {table}; source and target column order/type/nullability differ"
            )
        if any(c["generated"] or c["identity"] for c in source_columns):
            raise A124ImportError(
                f"table {table} uses generated/identity columns not supported by this import path"
            )
        if table in canonical_tables:
            canonical_names = list(canonical_tables[table])
            source_names = [c["name"] for c in source_columns]
            if source_names != canonical_names:
                raise A124ImportError(
                    f"live source table {table} does not match canonical A1.24 column inventory"
                )
        source_key = _key_columns(source_conn, source_schema, table)
        target_key = _key_columns(target_conn, target_schema, table)
        if source_key != target_key:
            raise A124ImportError(
                f"key mismatch for {table}: source {source_key}, target {target_key}"
            )
        if _has_null_key(source_conn, source_schema, table, source_key):
            raise A124ImportError(
                f"table {table} contains NULL in its import key {source_key}; refusing non-idempotent merge"
            )
        source_count = int(source_conn.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(source_schema), sql.Identifier(table)
            )
        ).fetchone()[0])
        target_count = int(target_conn.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(target_schema), sql.Identifier(table)
            )
        ).fetchone()[0])
        table_plans.append({
            "table": table, "columns": [c["name"] for c in source_columns],
            "key_columns": list(source_key), "source_rows": source_count,
            "target_rows_before": target_count,
        })

    source_sequences = _sequence_specs(source_conn, source_schema)
    target_sequences = _sequence_specs(target_conn, target_schema)
    missing_sequences = sorted(set(source_sequences) - set(target_sequences))
    if missing_sequences:
        raise A124ImportError(f"target schema is missing source sequences: {missing_sequences}")
    sequence_definition_drift = {
        name: {"source": spec, "target": target_sequences[name]}
        for name, spec in source_sequences.items() if spec != target_sequences[name]
    }
    if sequence_definition_drift:
        raise A124ImportError(f"sequence definition mismatch: {sequence_definition_drift}")
    source_owners = _sequence_owners(source_conn, source_schema)
    target_owners = _sequence_owners(target_conn, target_schema)
    owner_drift = {
        name: {"source": owner, "target": target_owners.get(name)}
        for name, owner in source_owners.items() if target_owners.get(name) != owner
    }
    if owner_drift:
        raise A124ImportError(f"sequence ownership mismatch: {owner_drift}")

    order = _table_order(source_tables, _foreign_keys(source_conn, source_schema))
    self_references = [fk for fk in _foreign_keys(source_conn, source_schema) if fk["child"] == fk["parent"]]
    self_order: dict[str, dict[str, str]] = {}
    for fk in self_references:
        if len(fk["child_columns"]) != 1 or len(fk["parent_columns"]) != 1:
            raise A124ImportError(
                f"composite self-referencing foreign key on {fk['child']} is not supported safely"
            )
        key = _key_columns(source_conn, source_schema, fk["child"])
        if len(key) != 1 or key[0] != fk["parent_columns"][0]:
            raise A124ImportError(
                f"self-referencing table {fk['child']} does not reference its single-column import key"
            )
        if fk["child"] in self_order:
            raise A124ImportError(f"multiple self-referencing foreign keys on {fk['child']} need a reviewed import order")
        self_order[fk["child"]] = {"foreign_key": fk["child_columns"][0], "key": key[0]}
    table_plan_by_name = {item["table"]: item for item in table_plans}
    ordered_plans = [table_plan_by_name[name] for name in order]
    for plan in ordered_plans:
        plan["self_reference"] = self_order.get(plan["table"])
    return {
        "source_schema": source_schema, "target_schema": target_schema,
        "source_table_count": len(source_tables), "canonical_table_count": len(canonical_tables),
        "table_order": order, "tables": ordered_plans,
        "source_sequence_count": len(source_sequences),
        "sequence_names": sorted(source_sequences),
        "source_rows_total": sum(item["source_rows"] for item in table_plans),
        "target_rows_before_total": sum(item["target_rows_before"] for item in table_plans),
        "mode": "dry-run",
    }


def _source_query(source_conn, source_schema: str, plan: dict[str, Any], cursor_name: str) -> tuple[Any, int]:
    table = plan["table"]
    columns = plan["columns"]
    self_ref = plan["self_reference"]
    if not self_ref:
        query = sql.SQL("SELECT {} FROM {}.{}").format(
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.Identifier(source_schema), sql.Identifier(table),
        )
        cursor = source_conn.cursor(name=cursor_name)
        cursor.execute(query)
        return cursor, int(plan["source_rows"])

    # For a simple self-referencing hierarchy, stream parents before children.
    # The count check below detects cycles or disconnected rows before target writes.
    key = self_ref["key"]
    parent = self_ref["foreign_key"]
    query = sql.SQL("""
        WITH RECURSIVE atd_import_tree AS (
            SELECT {key}, 0::bigint AS depth, ARRAY[{key}] AS visited
            FROM {schema}.{table}
            WHERE {parent} IS NULL
            UNION ALL
            SELECT child.{key}, tree.depth + 1, tree.visited || child.{key}
            FROM {schema}.{table} AS child
            JOIN atd_import_tree AS tree ON child.{parent}=tree.{key}
            WHERE NOT child.{key}=ANY(tree.visited)
        )
        SELECT {columns}
        FROM {schema}.{table} AS source_row
        JOIN atd_import_tree AS tree ON source_row.{key}=tree.{key}
        ORDER BY tree.depth, tree.{key}
    """).format(
        key=sql.Identifier(key), parent=sql.Identifier(parent),
        schema=sql.Identifier(source_schema), table=sql.Identifier(table),
        columns=sql.SQL(", ").join(sql.SQL("source_row.{}").format(sql.Identifier(column)) for column in columns),
    )
    cursor = source_conn.cursor(name=cursor_name)
    cursor.execute(query)
    return cursor, int(plan["source_rows"])


def import_data(source_conn, target_conn, source_schema: str, target_schema: str,
                canonical_tables: dict[str, dict[str, str]], *, apply: bool = False) -> dict[str, Any]:
    """Plan a complete row merge, or apply it in one target transaction.

    Source tables absent from the canonical core are treated as plugin tables:
    they are included only when an exactly shaped, keyed target table exists.
    Source-only/plugin-only objects are never silently skipped.
    """
    plan = _plan(source_conn, target_conn, source_schema, target_schema, canonical_tables)
    if not apply:
        return plan

    # Ensure self-referencing hierarchies are fully orderable before any target
    # mutation. A cycle or malformed parent chain fails closed.
    for table_plan in plan["tables"]:
        if table_plan["self_reference"]:
            cursor, expected = _source_query(
                source_conn, source_schema, table_plan,
                "atd_a124_check_" + re.sub(r"[^a-zA-Z0-9_]", "_", table_plan["table"])[:40],
            )
            try:
                count = sum(1 for _row in cursor)
            finally:
                cursor.close()
            if count != expected:
                raise A124ImportError(
                    f"self-referencing table {table_plan['table']} contains a cycle or unorderable parent chain"
                )

    source_sequences = _sequence_specs(source_conn, source_schema)
    source_owners = _sequence_owners(source_conn, source_schema)
    table_results: list[dict[str, Any]] = []
    with target_conn.transaction():
        for table_plan in plan["tables"]:
            target_conn.execute(
                sql.SQL("LOCK TABLE {}.{} IN SHARE ROW EXCLUSIVE MODE").format(
                    sql.Identifier(target_schema), sql.Identifier(table_plan["table"])
                )
            )
        target_conn.execute("SET CONSTRAINTS ALL DEFERRED")
        for index, table_plan in enumerate(plan["tables"]):
            table = table_plan["table"]
            columns = table_plan["columns"]
            stage = f"atd_a124_stage_{index:03d}"
            target_conn.execute(
                sql.SQL("CREATE TEMP TABLE {} (LIKE {}.{} INCLUDING DEFAULTS) ON COMMIT DROP").format(
                    sql.Identifier(stage), sql.Identifier(target_schema), sql.Identifier(table)
                )
            )
            source_cursor, expected = _source_query(
                source_conn, source_schema, table_plan, f"atd_a124_src_{index:03d}"
            )
            try:
                copy_query = sql.SQL("COPY {} ({}) FROM STDIN").format(
                    sql.Identifier(stage),
                    sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                )
                copied = 0
                with target_conn.cursor().copy(copy_query) as copy:
                    for row in source_cursor:
                        copy.write_row(row)
                        copied += 1
            finally:
                source_cursor.close()
            if copied != expected:
                raise A124ImportError(
                    f"source row count changed during import for {table}: planned {expected}, streamed {copied}"
                )
            key_columns = table_plan["key_columns"]
            updates = [column for column in columns if column not in key_columns]
            insert = sql.SQL("INSERT INTO {}.{} ({}) SELECT {} FROM {}").format(
                sql.Identifier(target_schema), sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                sql.Identifier(stage),
            )
            if updates:
                insert += sql.SQL(" ON CONFLICT ({}) DO UPDATE SET {}").format(
                    sql.SQL(", ").join(sql.Identifier(column) for column in key_columns),
                    sql.SQL(", ").join(
                        sql.SQL("{}=EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
                        for column in updates
                    ),
                )
            else:
                insert += sql.SQL(" ON CONFLICT ({}) DO NOTHING").format(
                    sql.SQL(", ").join(sql.Identifier(column) for column in key_columns)
                )
            result = target_conn.execute(insert)
            table_results.append({
                "table": table, "source_rows": copied,
                "rows_inserted_or_updated": int(result.rowcount),
                "key_columns": key_columns,
            })

        # ALTER SEQUENCE RESTART is transactional (unlike setval). Keep each
        # sequence ahead of both its source sequence state and imported owned IDs.
        for sequence_name in sorted(source_sequences):
            last_value, is_called = _sequence_state(source_conn, source_schema, sequence_name)
            owner = source_owners.get(sequence_name)
            maximum = None
            if owner:
                maximum = _owned_column_max(source_conn, source_schema, owner[0], owner[1])
            increment = source_sequences[sequence_name]["increment"]
            if maximum is not None and maximum >= last_value:
                next_value = maximum + increment
            elif is_called:
                next_value = last_value + increment
            else:
                next_value = last_value
            spec = source_sequences[sequence_name]
            if next_value < spec["min"] or next_value > spec["max"]:
                raise A124ImportError(
                    f"sequence {sequence_name} next value {next_value} is outside its configured bounds"
                )
            target_conn.execute(
                sql.SQL("ALTER SEQUENCE {}.{} RESTART WITH {}").format(
                    sql.Identifier(target_schema), sql.Identifier(sequence_name), sql.Literal(next_value)
                )
            )
    plan["mode"] = "apply"
    plan["tables"] = table_results
    plan["sequences_reconciled"] = len(source_sequences)
    plan["rows_inserted_or_updated_total"] = sum(item["rows_inserted_or_updated"] for item in table_results)
    return plan


def _database_identity(conn) -> tuple[str, str, str]:
    row = conn.execute(
        "SELECT current_database(), COALESCE(inet_server_addr()::text, ''), COALESCE(inet_server_port()::text, '')"
    ).fetchone()
    return str(row[0]), str(row[1]), str(row[2])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="atd-radius-a124-import",
        description="Dry-run or transactionally merge A1.24 database rows into a schema-compatible ATD database.",
    )
    parser.add_argument("--archive", type=Path, required=True, help="checksum-verified canonical IBSng-A1.24.tar.bz2")
    parser.add_argument("--source-dsn", required=True, help="read-only connection string for the legacy A1.24 database")
    parser.add_argument("--target-dsn", default=None, help="ATD target DSN (defaults to ATD_DATABASE_URL)")
    parser.add_argument("--source-schema", default="public")
    parser.add_argument("--target-schema", default="public")
    parser.add_argument("--apply", action="store_true", help="apply the import; default is a read-only dry run")
    parser.add_argument("--confirm-target", help="must exactly equal the target database name when --apply is used")
    args = parser.parse_args(argv)

    try:
        digest, source_inventory = read_a124_schema(str(args.archive))
        if digest != CANONICAL_A124_SHA256:
            raise A124ImportError(
                f"canonical archive SHA-256 mismatch: expected {CANONICAL_A124_SHA256}, got {digest}"
            )
        target_dsn = args.target_dsn or __import__("atd_radius.config", fromlist=["settings"]).settings.database_url
        with psycopg.connect(args.source_dsn) as source_conn, psycopg.connect(target_dsn) as target_conn:
            source_identity = _database_identity(source_conn)
            target_identity = _database_identity(target_conn)
            if source_identity == target_identity:
                raise A124ImportError("source and target resolve to the same PostgreSQL database")
            if args.apply and args.confirm_target != target_identity[0]:
                raise A124ImportError("--apply requires --confirm-target to exactly match the target database name")
            report = import_data(
                source_conn, target_conn, args.source_schema, args.target_schema,
                source_inventory["tables"], apply=args.apply,
            )
            report["canonical_archive_sha256"] = digest
            report["source_database"] = source_identity[0]
            report["target_database"] = target_identity[0]
            report["warning"] = (
                "Row data only. Legacy DDL, functions, rules, triggers, roles, and unmapped objects are not imported. "
                "Stop writes to the source and target for the maintenance window; take verified backups first."
            )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (A124ImportError, psycopg.Error, OSError, ValueError, KeyError) as exc:
        print(f"A1.24 import refused/failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
