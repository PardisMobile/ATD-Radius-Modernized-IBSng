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
