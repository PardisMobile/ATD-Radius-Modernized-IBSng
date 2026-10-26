"""Fail-closed, transactional A1.24 row import into an existing ATD schema.

This tool transfers data only. It never creates/drops tables and never imports
legacy functions, triggers, rules, or plugin DDL. Every source table must have
an exact target table/column shape and a stable unique key; otherwise it refuses
to proceed rather than silently omit or flatten data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from atd_radius.config import settings
from atd_radius.compatibility.a124_schema_parity import _normalize_constraint, _source_column_spec, read_a124_schema

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
               attribute.attidentity,
               pg_catalog.pg_get_expr(defaults.adbin, defaults.adrelid),
               collation_namespace.nspname,
               collation_row.collname
        FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid=relation.relnamespace
        JOIN pg_attribute AS attribute ON attribute.attrelid=relation.oid
        LEFT JOIN pg_attrdef AS defaults
          ON defaults.adrelid=relation.oid AND defaults.adnum=attribute.attnum
        LEFT JOIN pg_collation AS collation_row
          ON collation_row.oid=attribute.attcollation AND attribute.attcollation <> 0
        LEFT JOIN pg_namespace AS collation_namespace
          ON collation_namespace.oid=collation_row.collnamespace
        WHERE namespace.nspname=%s AND relation.relname=%s
          AND relation.relkind IN ('r', 'p')
          AND attribute.attnum > 0 AND NOT attribute.attisdropped
        ORDER BY attribute.attnum
        """, (schema, table)
    ).fetchall()
    return [
        {"name": str(name), "type": str(type_name), "nullable": bool(nullable),
         "generated": str(generated or ""), "identity": str(identity or ""),
         "default": _normalize_object_sql(str(default), schema) if default is not None else None,
         "collation": f"{collation_schema}.{collation_name}" if collation_name else ""}
        for name, type_name, nullable, generated, identity, default, collation_schema, collation_name in rows
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


def _constraint_signatures(conn, schema: str) -> set[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT table_class.relname, pg_catalog.pg_get_constraintdef(constraint_row.oid, true)
        FROM pg_constraint AS constraint_row
        JOIN pg_class AS table_class ON table_class.oid=constraint_row.conrelid
        JOIN pg_namespace AS namespace ON namespace.oid=table_class.relnamespace
        WHERE namespace.nspname=%s AND constraint_row.contype IN ('p', 'f', 'u', 'c', 'x')
        ORDER BY table_class.relname, constraint_row.contype, constraint_row.oid
        """, (schema,)
    ).fetchall()
    signatures = set()
    for table, definition in rows:
        normalized = re.sub(rf"\b{re.escape(schema)}\.", "", str(definition), flags=re.I)
        signatures.add((str(table).lower(), _normalize_constraint(normalized)))
    return signatures

def _table_signatures(conn, schema: str, tables: set[str]) -> set[tuple[Any, ...]]:
    """Capture table behavior that can change row visibility or write semantics."""
    rows = conn.execute(
        """
        SELECT relation.relname, relation.relkind, relation.relpersistence,
               relation.relrowsecurity, relation.relforcerowsecurity,
               relation.relreplident,
               COALESCE(pg_catalog.pg_get_partkeydef(relation.oid), ''),
               COALESCE(pg_catalog.pg_get_expr(relation.relpartbound, relation.oid), ''),
               COALESCE((SELECT parent.relname
                         FROM pg_inherits AS inheritance
                         JOIN pg_class AS parent ON parent.oid=inheritance.inhparent
                         WHERE inheritance.inhrelid=relation.oid
                         ORDER BY parent.relname LIMIT 1), ''),
               COALESCE(array_to_string(relation.reloptions, ','), '')
        FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid=relation.relnamespace
        WHERE namespace.nspname=%s AND relation.relkind IN ('r', 'p')
        ORDER BY relation.relname
        """, (schema,)
    ).fetchall()
    return {
        (str(name), str(kind), str(persistence), bool(row_security),
         bool(force_row_security), str(replica_identity),
         _normalize_object_sql(str(partition_key), schema),
         _normalize_object_sql(str(partition_bound), schema),
         str(partition_parent), str(table_options))
        for name, kind, persistence, row_security, force_row_security,
            replica_identity, partition_key, partition_bound, partition_parent,
            table_options in rows
        if str(name) in tables
    }


def _policy_signatures(conn, schema: str, tables: set[str]) -> set[tuple[str, str, str, str, str, str, str]]:
    """Compare RLS policy definitions, including role scope and expressions."""
    rows = conn.execute(
        """
        SELECT tablename, policyname, permissive, roles, cmd, qual, with_check
        FROM pg_policies
        WHERE schemaname=%s
        ORDER BY tablename, policyname
        """, (schema,)
    ).fetchall()
    return {
        (str(table), str(name), str(permissive), str(roles), str(command),
         _normalize_object_sql(str(qual), schema) if qual is not None else "",
         _normalize_object_sql(str(with_check), schema) if with_check is not None else "")
        for table, name, permissive, roles, command, qual, with_check in rows
        if str(table) in tables
    }


def _index_signatures(conn, schema: str, tables: set[str]) -> set[tuple[str, str, str]]:
    """Compare all explicit and constraint-backed index definitions before row writes."""
    rows = conn.execute(
        """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname=%s
        ORDER BY tablename, indexname
        """, (schema,)
    ).fetchall()
    return {
        (str(table), str(name), _normalize_object_sql(str(definition), schema))
        for table, name, definition in rows if str(table) in tables
    }



def _normalize_object_sql(value: str, schema: str) -> str:
    normalized = re.sub(rf"\b{re.escape(schema)}\.", "", value, flags=re.I)
    return re.sub(r"\s+", " ", normalized).strip()


def _rules(conn, schema: str, tables: set[str]) -> set[tuple[str, str, str]]:
    rows = conn.execute(
        "SELECT tablename, rulename, definition FROM pg_rules WHERE schemaname=%s",
        (schema,)
    ).fetchall()
    return {
        (str(table), str(name), _normalize_object_sql(str(definition), schema))
        for table, name, definition in rows if str(table) in tables
    }


def _triggers(conn, schema: str, tables: set[str]) -> set[tuple[str, str, str, str, str]]:
    rows = conn.execute(
        """
        SELECT table_class.relname, trigger.tgname, trigger.tgenabled,
               pg_catalog.pg_get_triggerdef(trigger.oid, true),
               pg_catalog.pg_get_functiondef(trigger.tgfoid)
        FROM pg_trigger AS trigger
        JOIN pg_class AS table_class ON table_class.oid=trigger.tgrelid
        JOIN pg_namespace AS namespace ON namespace.oid=table_class.relnamespace
        WHERE namespace.nspname=%s AND NOT trigger.tgisinternal
        ORDER BY table_class.relname, trigger.tgname
        """, (schema,)
    ).fetchall()
    return {
        (str(table), str(name), str(enabled),
         _normalize_object_sql(str(definition), schema),
         _normalize_object_sql(str(function_definition), schema))
        for table, name, enabled, definition, function_definition in rows
        if str(table) in tables
    }


def _functions(conn, schema: str) -> set[tuple[str, str, str, str]]:
    rows = conn.execute(
        """
        SELECT procedure.proname,
               pg_catalog.pg_get_function_identity_arguments(procedure.oid),
               procedure.prokind,
               pg_catalog.pg_get_functiondef(procedure.oid)
        FROM pg_proc AS procedure
        JOIN pg_namespace AS namespace ON namespace.oid=procedure.pronamespace
        WHERE namespace.nspname=%s AND procedure.prokind IN ('f', 'p')
        ORDER BY procedure.proname, pg_catalog.pg_get_function_identity_arguments(procedure.oid)
        """, (schema,)
    ).fetchall()
    return {
        (str(name), str(arguments), str(kind), _normalize_object_sql(str(definition), schema))
        for name, arguments, kind, definition in rows
    }


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
          canonical_tables: dict[str, dict[str, str]],
          canonical_primary_keys: dict[str, set[str]] | None = None) -> dict[str, Any]:
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
        source_shape = [
            (c["name"], c["type"], c["nullable"], c["generated"], c["identity"], c["default"], c["collation"])
            for c in source_columns
        ]
        target_shape = [
            (c["name"], c["type"], c["nullable"], c["generated"], c["identity"], c["default"], c["collation"])
            for c in target_columns
        ]
        if source_shape != target_shape:
            raise A124ImportError(
                f"schema mismatch for {table}; source and target column order/type/nullability/default/collation differ"
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
            if canonical_primary_keys is not None:
                source_by_name = {column["name"]: column for column in source_columns}
                for column, declaration in canonical_tables[table].items():
                    spec = _source_column_spec(
                        declaration, column in canonical_primary_keys.get(table, set())
                    )
                    actual = source_by_name[column]
                    actual_type = re.sub(r"\\s+", " ", str(actual["type"]).lower())
                    if actual_type != spec["type"] or actual["nullable"] != spec["nullable"]:
                        raise A124ImportError(
                            f"live source table {table}.{column} differs from canonical A1.24 "
                            f"type/nullability: expected {spec['type']} nullable={spec['nullable']}, "
                            f"found {actual_type} nullable={actual['nullable']}"
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

    source_table_set = set(source_tables)
    source_constraints = {
        item for item in _constraint_signatures(source_conn, source_schema) if item[0] in source_table_set
    }
    target_constraints = {
        item for item in _constraint_signatures(target_conn, target_schema) if item[0] in source_table_set
    }
    if source_constraints != target_constraints:
        raise A124ImportError(
            "source/target constraint definitions differ; "
            f"missing in target={sorted(source_constraints - target_constraints)}, "
            f"extra in target={sorted(target_constraints - source_constraints)}"
        )

    source_table_signatures = _table_signatures(source_conn, source_schema, source_table_set)
    target_table_signatures = _table_signatures(target_conn, target_schema, source_table_set)
    if source_table_signatures != target_table_signatures:
        raise A124ImportError(
            "source/target table behavior differs; "
            f"missing in target={sorted(source_table_signatures - target_table_signatures)}, "
            f"extra in target={sorted(target_table_signatures - source_table_signatures)}"
        )

    source_policies = _policy_signatures(source_conn, source_schema, source_table_set)
    target_policies = _policy_signatures(target_conn, target_schema, source_table_set)
    if source_policies != target_policies:
        raise A124ImportError(
            "source/target row-level security policies differ; "
            f"missing in target={sorted(source_policies - target_policies)}, "
            f"extra in target={sorted(target_policies - source_policies)}"
        )

    source_indexes = _index_signatures(source_conn, source_schema, source_table_set)
    target_indexes = _index_signatures(target_conn, target_schema, source_table_set)
    if source_indexes != target_indexes:
        raise A124ImportError(
            "source/target index definitions differ; "
            f"missing in target={sorted(source_indexes - target_indexes)}, "
            f"extra in target={sorted(target_indexes - source_indexes)}"
        )

    source_rules = _rules(source_conn, source_schema, source_table_set)
    target_rules = _rules(target_conn, target_schema, source_table_set)
    if source_rules != target_rules:
        raise A124ImportError(
            "source/target rule definitions differ; "
            f"missing in target={sorted(source_rules - target_rules)}, "
            f"extra in target={sorted(target_rules - source_rules)}"
        )
    source_triggers = _triggers(source_conn, source_schema, source_table_set)
    target_triggers = _triggers(target_conn, target_schema, source_table_set)
    if source_triggers != target_triggers:
        raise A124ImportError(
            "source/target trigger definitions differ; "
            f"missing in target={sorted(source_triggers - target_triggers)}, "
            f"extra in target={sorted(target_triggers - source_triggers)}"
        )
    source_functions = _functions(source_conn, source_schema)
    target_functions = _functions(target_conn, target_schema)
    missing_functions = sorted(source_functions - target_functions)
    if missing_functions:
        raise A124ImportError(
            "source functions/procedures are missing or differ in target; "
            f"review required: {missing_functions}"
        )

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
                canonical_tables: dict[str, dict[str, str]], *, apply: bool = False,
                canonical_primary_keys: dict[str, set[str]] | None = None) -> dict[str, Any]:
    """Plan a complete row merge, or apply it in one target transaction.

    Source tables absent from the canonical core are treated as plugin tables:
    they are included only when an exactly shaped, keyed target table exists.
    Source-only/plugin-only objects are never silently skipped.
    """
    plan = _plan(source_conn, target_conn, source_schema, target_schema, canonical_tables, canonical_primary_keys)
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

    table_results: list[dict[str, Any]] = []
    sequence_results: list[dict[str, Any]] = []
    with target_conn.transaction():
        for table_plan in plan["tables"]:
            target_conn.execute(
                sql.SQL("LOCK TABLE {}.{} IN SHARE ROW EXCLUSIVE MODE").format(
                    sql.Identifier(target_schema), sql.Identifier(table_plan["table"])
                )
            )
        # The first plan is advisory: target DDL could change between preflight and
        # lock acquisition. Re-run the complete compatibility gate while every
        # source table's target counterpart is locked, before creating staging
        # tables or writing any rows.
        locked_plan = _plan(
            source_conn, target_conn, source_schema, target_schema,
            canonical_tables, canonical_primary_keys,
        )
        planned_tables = [item["table"] for item in plan["tables"]]
        locked_tables = [item["table"] for item in locked_plan["tables"]]
        if locked_tables != planned_tables:
            raise A124ImportError(
                "source table inventory changed between preflight and locked validation; "
                "no data was imported"
            )
        plan = locked_plan
        # Refresh sequence metadata only after the locked schema check.
        source_sequences = _sequence_specs(source_conn, source_schema)
        source_owners = _sequence_owners(source_conn, source_schema)
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
            key_join = sql.SQL(" AND ").join(
                sql.SQL("target_row.{} = stage_row.{}").format(
                    sql.Identifier(column), sql.Identifier(column)
                ) for column in key_columns
            )
            value_drift = sql.SQL(" OR ").join(
                sql.SQL("target_row.{} IS DISTINCT FROM stage_row.{}").format(
                    sql.Identifier(column), sql.Identifier(column)
                ) for column in columns
            )
            mismatches = int(target_conn.execute(
                sql.SQL("""
                    SELECT count(*)
                    FROM {} AS stage_row
                    LEFT JOIN {}.{} AS target_row ON {}
                    WHERE {} OR {}
                """).format(
                    sql.Identifier(stage), sql.Identifier(target_schema), sql.Identifier(table),
                    key_join,
                    sql.SQL(" OR ").join(sql.SQL("target_row.{} IS NULL").format(sql.Identifier(key))
                                         for key in key_columns),
                    value_drift,
                )
            ).fetchone()[0])
            if mismatches:
                raise A124ImportError(
                    f"post-merge row parity failed for {table}: {mismatches} source rows differ from target"
                )
            target_rows_after = int(target_conn.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(
                    sql.Identifier(target_schema), sql.Identifier(table)
                )
            ).fetchone()[0])
            table_results.append({
                "table": table,
                "source_rows": copied,
                "target_rows_before": table_plan["target_rows_before"],
                "target_rows_after": target_rows_after,
                "target_only_rows_after": target_rows_after - copied,
                "rows_inserted_or_updated": int(result.rowcount),
                "rows_verified": copied - mismatches,
                "key_columns": key_columns,
            })

        # ALTER SEQUENCE RESTART is transactional (unlike setval). Keep each
        # sequence ahead of both its source sequence state and imported owned IDs.
        for sequence_name in sorted(source_sequences):
            last_value, is_called = _sequence_state(source_conn, source_schema, sequence_name)
            target_before_value, target_before_called = _sequence_state(target_conn, target_schema, sequence_name)
            owner = source_owners.get(sequence_name)
            maximum = None
            if owner:
                source_maximum = _owned_column_max(source_conn, source_schema, owner[0], owner[1])
                target_maximum = _owned_column_max(target_conn, target_schema, owner[0], owner[1])
                candidates = [value for value in (source_maximum, target_maximum) if value is not None]
                maximum = max(candidates) if candidates else None
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
            target_after_value, target_after_called = _sequence_state(target_conn, target_schema, sequence_name)
            sequence_results.append({
                "sequence": sequence_name,
                "source_last_value": last_value,
                "source_is_called": is_called,
                "target_last_value_before": target_before_value,
                "target_is_called_before": target_before_called,
                "target_next_value_after": target_after_value,
                "target_is_called_after": target_after_called,
                "restart_value": next_value,
                "owned_by": list(owner) if owner else None,
                "maximum_owned_id": maximum,
            })
    plan["mode"] = "apply"
    plan["sequence_results"] = sequence_results
    plan["tables"] = table_results
    plan["sequences_reconciled"] = len(source_sequences)
    plan["rows_inserted_or_updated_total"] = sum(item["rows_inserted_or_updated"] for item in table_results)
    plan["rows_verified_total"] = sum(item["rows_verified"] for item in table_results)
    plan["target_rows_after_total"] = sum(item["target_rows_after"] for item in table_results)
    plan["target_only_rows_after_total"] = sum(item["target_only_rows_after"] for item in table_results)
    return plan


def _write_report(path: Path, report: dict[str, Any]) -> None:
    """Create a private JSON evidence file without overwriting an earlier report."""
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            os.chmod(path, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise A124ImportError(f"report file already exists; refusing to overwrite: {path}") from exc
    except OSError:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


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
    parser.add_argument(
        "--report-file", type=Path,
        help="write a private JSON audit report to a new file (existing files are never overwritten)",
    )
    args = parser.parse_args(argv)

    try:
        if args.report_file is not None:
            if args.report_file.exists():
                raise A124ImportError(f"report file already exists; refusing to overwrite: {args.report_file}")
            if not args.report_file.parent.is_dir():
                raise A124ImportError(f"report directory does not exist: {args.report_file.parent}")
        digest, source_inventory = read_a124_schema(str(args.archive))
        if digest != CANONICAL_A124_SHA256:
            raise A124ImportError(
                f"canonical archive SHA-256 mismatch: expected {CANONICAL_A124_SHA256}, got {digest}"
            )
        target_dsn = args.target_dsn or settings.database_url
        with psycopg.connect(args.source_dsn) as source_conn, psycopg.connect(target_dsn) as target_conn:
            # One repeatable, read-only source snapshot prevents mixed versions
            # of a table set while the operator is importing a live database.
            source_conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            source_identity = _database_identity(source_conn)
            target_identity = _database_identity(target_conn)
            if source_identity == target_identity:
                raise A124ImportError("source and target resolve to the same PostgreSQL database")
            if args.apply and args.confirm_target != target_identity[0]:
                raise A124ImportError("--apply requires --confirm-target to exactly match the target database name")
            report = import_data(
                source_conn, target_conn, args.source_schema, args.target_schema,
                source_inventory["tables"], apply=args.apply,
                canonical_primary_keys=source_inventory.get("primary_keys"),
            )
            report["canonical_archive_sha256"] = digest
            report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
            report["source_database"] = source_identity[0]
            report["source_server_address"] = source_identity[1]
            report["source_server_port"] = source_identity[2]
            report["target_database"] = target_identity[0]
            report["target_server_address"] = target_identity[1]
            report["target_server_port"] = target_identity[2]
            report["warning"] = (
                "Row data only. Legacy DDL, functions, rules, triggers, roles, and unmapped objects are not imported. "
                "Stop writes to the source and target for the maintenance window; take verified backups first."
            )
        rendered = json.dumps(report, indent=2, sort_keys=True)
        if args.report_file is not None:
            _write_report(args.report_file, report)
            print(f"Audit report written: {args.report_file}")
        print(rendered)
        return 0
    except (A124ImportError, psycopg.Error, OSError, ValueError, KeyError) as exc:
        print(f"A1.24 import refused/failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
