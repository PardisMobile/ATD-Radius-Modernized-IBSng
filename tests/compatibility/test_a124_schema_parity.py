import pytest
from atd_radius.compatibility.a124_schema_parity import (
    compare_inventory,
    compare_schema,
    parse_a124_inventory,
    parse_a124_tables,
)


def test_parser_handles_nested_types_constraints_and_comments():
    sql = """
    -- create table ignored (id int);
    CREATE TABLE admins (
      admin_id integer primary key, username text unique,
      deposit numeric(12,2) default 0,
      note text default 'value, still one column',
      CONSTRAINT admins_check CHECK (deposit >= 0)
    );
    create table child (
      id bigint, admin_id integer references admins(admin_id),
      primary key (id, admin_id)
    );
    """
    parsed = parse_a124_tables(sql)
    assert list(parsed) == ["admins", "child"]
    assert list(parsed["admins"]) == ["admin_id", "username", "deposit", "note"]
    assert parsed["admins"]["deposit"] == "numeric(12,2) default 0"
    assert parsed["child"]["admin_id"] == "integer references admins(admin_id)"


def test_parser_fails_closed_on_malformed_or_duplicate_schema():
    with pytest.raises(ValueError, match="Unterminated"):
        parse_a124_tables("CREATE TABLE users (id integer")
    with pytest.raises(ValueError, match="Duplicate table"):
        parse_a124_tables("CREATE TABLE users (id integer); CREATE TABLE users (id integer);")


def test_comparison_reports_missing_and_extra_tables_and_columns():
    source = {"users": {"id": "integer", "username": "text"}, "admins": {"id": "integer"}}
    report = compare_schema(source, [("users", "id"), ("users", "legacy_note"), ("audit", "id")])
    assert report["missing_tables"] == ["admins"]
    assert report["extra_tables"] == ["audit"]
    assert report["missing_columns"] == {"users": ["username"]}
    assert report["extra_columns"] == {"users": ["legacy_note"]}
    assert report["drift_count"] == 4
    assert report["matches_by_name"] is False


def test_comparison_is_case_insensitive_for_an_exact_inventory():
    report = compare_schema({"Users": {"UserName": "text"}}, [("users", "username")])
    assert report["matches_by_name"] is True
    assert report["drift_count"] == 0


def test_inventory_includes_explicit_indexes_sequences_and_serial_sequences():
    inventory = parse_a124_inventory("""
        CREATE TABLE admins (admin_id integer primary key, username text);
        CREATE SEQUENCE admins_id_seq;
        CREATE TABLE audit_events (event_id serial primary key, detail text);
        CREATE UNIQUE INDEX admins_username_idx ON admins (username);
    """)
    assert inventory["indexes"] == ["admins_username_idx"]
    assert inventory["sequences"] == ["admins_id_seq", "audit_events_event_id_seq"]
    assert set(inventory["tables"]) == {"admins", "audit_events"}


def test_inventory_comparison_reports_index_and_sequence_drift():
    source = {
        "tables": {"users": {"id": "integer"}},
        "indexes": ["users_username_idx"],
        "sequences": ["users_id_seq"],
    }
    target = {
        "columns": [("users", "id")],
        "indexes": ["users_legacy_idx"],
        "sequences": ["users_old_id_seq"],
    }
    report = compare_inventory(source, target)
    assert report["missing_indexes"] == ["users_username_idx"]
    assert report["extra_indexes"] == ["users_legacy_idx"]
    assert report["missing_sequences"] == ["users_id_seq"]
    assert report["extra_sequences"] == ["users_old_id_seq"]
    assert report["inventory_drift_count"] == 4
    assert report["matches_inventory_by_name"] is False


def test_comment_stripping_does_not_delete_comment_markers_inside_strings():
    parsed = parse_a124_tables("CREATE TABLE messages (body text DEFAULT 'keep -- this');")
    assert parsed["messages"]["body"] == "text DEFAULT 'keep -- this'"


def test_checked_in_a124_migration_inventory_is_complete_for_static_ddl():
    from pathlib import Path

    migration = Path(__file__).resolve().parents[2] / "migrations" / "001_initial.sql"
    inventory = parse_a124_inventory(migration.read_text(encoding="utf-8"))
    tables = inventory["tables"]
    assert len(tables) == 51
    assert sum(len(columns) for columns in tables.values()) == 224
    assert len(inventory["indexes"]) == 19
    assert len(inventory["sequences"]) == 26


def test_inventory_compares_type_default_and_nullability_metadata():
    source = parse_a124_inventory("""
        CREATE TABLE users (
          user_id integer,
          active boolean DEFAULT 't',
          credit numeric(12,2) DEFAULT 0,
          created_at timestamp DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (user_id)
        );
    """)
    target = {
        "columns": [
            {"table": "users", "column": "user_id", "type": "integer", "nullable": False, "default": None},
            {"table": "users", "column": "active", "type": "boolean", "nullable": True, "default": "true"},
            {"table": "users", "column": "credit", "type": "numeric(12,2)", "nullable": True, "default": "0"},
            {"table": "users", "column": "created_at", "type": "timestamp without time zone", "nullable": True,
             "default": "CURRENT_TIMESTAMP"},
        ],
        "indexes": [],
        "sequences": [],
    }
    report = compare_inventory(source, target)
    assert report["column_definition_drift_count"] == 0
    assert report["matches_column_definitions"] is True


def test_inventory_reports_real_column_definition_drift():
    source = parse_a124_inventory("CREATE TABLE users (id integer PRIMARY KEY, enabled boolean DEFAULT true);")
    target = {
        "columns": [
            {"table": "users", "column": "id", "type": "bigint", "nullable": True, "default": None},
            {"table": "users", "column": "enabled", "type": "boolean", "nullable": True, "default": "false"},
        ],
        "indexes": [],
        "sequences": [],
    }
    report = compare_inventory(source, target)
    drift = {(item["column"], item["field"]) for item in report["column_definition_drift"]}
    assert drift == {("id", "type"), ("id", "nullable"), ("enabled", "default")}


def test_inventory_extracts_inline_and_table_level_constraints():
    inventory = parse_a124_inventory("""
        CREATE TABLE admins (
            admin_id integer PRIMARY KEY,
            username text UNIQUE,
            deposit numeric(12,2),
            CONSTRAINT admins_deposit_nonnegative CHECK (deposit >= 0)
        );
        CREATE TABLE child (
            child_id integer PRIMARY KEY,
            admin_id integer REFERENCES admins(admin_id),
            CONSTRAINT child_admin_fk FOREIGN KEY (admin_id) REFERENCES admins(admin_id)
        );
    """)
    constraints = {(item["table"], item["definition"]) for item in inventory["constraints"]}
    assert ("admins", "primary key(admin_id)") in constraints
    assert ("admins", "unique(username)") in constraints
    assert ("admins", "check(deposit >= 0)") in constraints
    assert ("child", "primary key(child_id)") in constraints
    assert ("child", "foreign key(admin_id) references admins(admin_id)") in constraints


def test_inventory_comparison_reports_constraint_drift_on_shared_tables_only():
    source = {
        "tables": {"users": {"id": "integer"}, "legacy_only": {"id": "integer"}},
        "indexes": [], "sequences": [],
        "constraints": [
            {"table": "users", "definition": "primary key(id)"},
            {"table": "legacy_only", "definition": "primary key(id)"},
        ],
    }
    target = {
        "columns": [
            {"table": "users", "column": "id", "type": "integer", "nullable": False, "default": None},
            {"table": "atd_only", "column": "id", "type": "integer", "nullable": False, "default": None},
        ],
        "indexes": [], "sequences": [],
        "constraints": [
            {"table": "users", "definition": "unique(id)"},
            {"table": "atd_only", "definition": "primary key(id)"},
        ],
    }
    report = compare_inventory(source, target)
    assert report["constraint_drift_count"] == 2
    assert report["missing_constraints"] == [{"table": "users", "definition": "primary key(id)"}]
    assert report["extra_constraints"] == [{"table": "users", "definition": "unique(id)"}]
    assert report["matches_all_audited_fields"] is False
