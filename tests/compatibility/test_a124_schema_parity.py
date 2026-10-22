import pytest
from atd_radius.compatibility.a124_schema_parity import compare_schema, parse_a124_tables


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
