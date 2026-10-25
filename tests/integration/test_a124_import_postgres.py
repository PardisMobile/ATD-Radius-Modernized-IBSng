"""PostgreSQL acceptance tests for fail-closed A1.24 row import."""
from __future__ import annotations

import os
import uuid

import psycopg
from psycopg import sql
import pytest

from atd_radius.cli.a124_import import A124ImportError, import_data


@pytest.fixture
def import_schemas():
    base_dsn = os.environ.get("ATD_TEST_DATABASE_URL")
    if not base_dsn:
        pytest.skip("ATD_TEST_DATABASE_URL is required for A1.24 import acceptance")
    suffix = uuid.uuid4().hex[:10]
    source_schema = "a124_src_" + suffix
    target_schema = "a124_tgt_" + suffix
    with psycopg.connect(base_dsn) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(source_schema)))
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(target_schema)))
        conn.execute(sql.SQL("CREATE TABLE {}.parent (id integer PRIMARY KEY, label text NOT NULL)").format(sql.Identifier(source_schema)))
        conn.execute(sql.SQL("CREATE TABLE {}.child (id integer PRIMARY KEY, parent_id integer REFERENCES {}.parent(id), value text)").format(sql.Identifier(source_schema), sql.Identifier(source_schema)))
        conn.execute(sql.SQL("CREATE SEQUENCE {}.parent_id_seq").format(sql.Identifier(source_schema)))
        conn.execute(sql.SQL("ALTER SEQUENCE {}.parent_id_seq OWNED BY {}.parent.id").format(sql.Identifier(source_schema), sql.Identifier(source_schema)))
        conn.execute(sql.SQL("ALTER TABLE {}.parent ALTER COLUMN id SET DEFAULT nextval(%s::regclass)").format(sql.Identifier(source_schema)), (f"{source_schema}.parent_id_seq",))
        conn.execute(sql.SQL("CREATE TABLE {}.parent (id integer PRIMARY KEY, label text NOT NULL)").format(sql.Identifier(target_schema)))
        conn.execute(sql.SQL("CREATE TABLE {}.child (id integer PRIMARY KEY, parent_id integer REFERENCES {}.parent(id), value text)").format(sql.Identifier(target_schema), sql.Identifier(target_schema)))
        conn.execute(sql.SQL("CREATE SEQUENCE {}.parent_id_seq").format(sql.Identifier(target_schema)))
        conn.execute(sql.SQL("ALTER SEQUENCE {}.parent_id_seq OWNED BY {}.parent.id").format(sql.Identifier(target_schema), sql.Identifier(target_schema)))
        conn.execute(sql.SQL("ALTER TABLE {}.parent ALTER COLUMN id SET DEFAULT nextval(%s::regclass)").format(sql.Identifier(target_schema)), (f"{target_schema}.parent_id_seq",))
        conn.execute(sql.SQL("INSERT INTO {}.parent VALUES (1, 'old target')").format(sql.Identifier(target_schema)))
        conn.execute(sql.SQL("INSERT INTO {}.parent VALUES (1, 'source row'), (2, 'parent')").format(sql.Identifier(source_schema)))
        conn.execute(sql.SQL("INSERT INTO {}.child VALUES (10, 2, 'child')").format(sql.Identifier(source_schema)))
        conn.execute(sql.SQL("SELECT setval(%s::regclass, 2, true)").format(), (f"{source_schema}.parent_id_seq",))
    try:
        yield base_dsn, source_schema, target_schema
    finally:
        with psycopg.connect(base_dsn) as conn:
            conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(source_schema)))
            conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(target_schema)))


def test_dry_run_reports_rows_without_mutating_target(import_schemas):
    dsn, source_schema, target_schema = import_schemas
    with psycopg.connect(dsn) as source, psycopg.connect(dsn) as target:
        report = import_data(
            source, target, source_schema, target_schema,
            {"parent": {"id": "integer", "label": "text"}, "child": {"id": "integer", "parent_id": "integer", "value": "text"}},
        )
        assert report["mode"] == "dry-run"
        assert report["source_rows_total"] == 3
        assert target.execute(sql.SQL("SELECT label FROM {}.parent WHERE id=1").format(sql.Identifier(target_schema))).fetchone()[0] == "old target"


def test_apply_merges_rows_in_fk_order_and_reconciles_sequences(import_schemas):
    dsn, source_schema, target_schema = import_schemas
    with psycopg.connect(dsn) as source, psycopg.connect(dsn) as target:
        report = import_data(
            source, target, source_schema, target_schema,
            {"parent": {"id": "integer", "label": "text"}, "child": {"id": "integer", "parent_id": "integer", "value": "text"}},
            apply=True,
        )
        assert report["mode"] == "apply"
        assert target.execute(sql.SQL("SELECT label FROM {}.parent WHERE id=1").format(sql.Identifier(target_schema))).fetchone()[0] == "source row"
        assert target.execute(sql.SQL("SELECT parent_id, value FROM {}.child WHERE id=10").format(sql.Identifier(target_schema))).fetchone() == (2, "child")
        assert target.execute(sql.SQL("SELECT nextval(%s::regclass)").format(), (f"{target_schema}.parent_id_seq",)).fetchone()[0] == 3


def test_import_refuses_unmapped_source_tables(import_schemas):
    dsn, source_schema, target_schema = import_schemas
    with psycopg.connect(dsn) as source, psycopg.connect(dsn) as target:
        source.execute(sql.SQL("CREATE TABLE {}.unmapped (payload text)").format(sql.Identifier(source_schema)))
        with pytest.raises(A124ImportError, match="missing source/plugin tables"):
            import_data(
                source, target, source_schema, target_schema,
                {"parent": {"id": "integer", "label": "text"}, "child": {"id": "integer", "parent_id": "integer", "value": "text"}},
            )


def test_import_refuses_self_reference_cycles_before_target_writes(import_schemas):
    dsn, source_schema, target_schema = import_schemas
    with psycopg.connect(dsn) as source, psycopg.connect(dsn) as target:
        source.execute(sql.SQL("CREATE TABLE {}.tree (id integer PRIMARY KEY, parent_id integer REFERENCES {}.tree(id))").format(sql.Identifier(source_schema), sql.Identifier(source_schema)))
        target.execute(sql.SQL("CREATE TABLE {}.tree (id integer PRIMARY KEY, parent_id integer REFERENCES {}.tree(id))").format(sql.Identifier(target_schema), sql.Identifier(target_schema)))
        source.execute(sql.SQL("INSERT INTO {}.tree VALUES (1, 2), (2, 1)").format(sql.Identifier(source_schema)))
        with pytest.raises(A124ImportError, match="cycle or unorderable"):
            import_data(
                source, target, source_schema, target_schema,
                {"parent": {"id": "integer", "label": "text"}, "child": {"id": "integer", "parent_id": "integer", "value": "text"}},
                apply=True,
            )
        assert target.execute(sql.SQL("SELECT count(*) FROM {}.tree").format(sql.Identifier(target_schema))).fetchone()[0] == 0


def test_import_refuses_keyless_tables(import_schemas):
    dsn, source_schema, target_schema = import_schemas
    with psycopg.connect(dsn) as source, psycopg.connect(dsn) as target:
        source.execute(sql.SQL("CREATE TABLE {}.keyless (payload text)").format(sql.Identifier(source_schema)))
        target.execute(sql.SQL("CREATE TABLE {}.keyless (payload text)").format(sql.Identifier(target_schema)))
        with pytest.raises(A124ImportError, match="no simple primary/unique key"):
            import_data(
                source, target, source_schema, target_schema,
                {"parent": {"id": "integer", "label": "text"}, "child": {"id": "integer", "parent_id": "integer", "value": "text"}},
            )


def test_import_refuses_canonical_source_type_drift(import_schemas):
    dsn, source_schema, target_schema = import_schemas
    with psycopg.connect(dsn) as source, psycopg.connect(dsn) as target:
        with pytest.raises(A124ImportError, match="differs from canonical A1.24"):
            import_data(
                source, target, source_schema, target_schema,
                {"parent": {"id": "bigint", "label": "text"}, "child": {"id": "integer", "parent_id": "integer", "value": "text"}},
                canonical_primary_keys={"parent": {"id"}, "child": {"id"}},
            )
