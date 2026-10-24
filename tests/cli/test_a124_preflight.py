from __future__ import annotations

import re
import pytest

from atd_radius.cli.a124_preflight import (
    CANONICAL_A124_SHA256,
    _defs_expected,
    _function_signatures,
    _normalize_default,
    _source_column_spec,
    source_inventory,
    _source_rules,
    _normalize_rule_condition,
    _function_definitions,
    _initial_state_expectations,
    _initial_admin_seed,
    _initial_god_permission_seed,
    _seed_values_equal,
    _source_constraint_signatures,
    _source_index_details,
    _normalize_check_expression,
    _normalize_index_sql,
    _has_required_columns,
    _native_table_trigger_drift,
    _source_sequence_specs,
    _sequence_definition_drift,
)


def test_source_inventory_reads_canonical_a124_schema_objects():
    tables_sql = """
      -- create table ignored (bad int);
      CREATE TABLE admins (admin_id integer PRIMARY KEY, username text unique, note text DEFAULT 'a,b');
      CREATE SEQUENCE admins_id_seq;
      CREATE UNIQUE INDEX admins_name_idx ON admins(username);
      CREATE TABLE serials (id serial PRIMARY KEY);
    """
    functions_sql = "CREATE OR REPLACE FUNCTION insert_user_attr(bigint, text, text) RETURNS integer AS 'begin return 1; end;' LANGUAGE plpgsql;"
    result = source_inventory(tables_sql, functions_sql)
    assert set(result["tables"]) == {"admins", "serials"}
    assert result["tables"]["admins"] == {"admin_id", "username", "note"}
    assert result["indexes"] == {"admins_name_idx"}
    assert result["sequences"] == {"admins_id_seq", "serials_id_seq"}
    assert result["sequence_owners"] == {"serials_id_seq": {"table": "serials", "column": "id"}}
    assert result["functions"] == {"insert_user_attr"}


def test_source_inventory_rejects_malformed_or_duplicate_tables():
    with pytest.raises(ValueError, match="Unterminated"):
        source_inventory("CREATE TABLE users (id integer", "CREATE FUNCTION f() RETURNS integer AS 'x';")
    with pytest.raises(ValueError, match="Duplicate"):
        source_inventory("CREATE TABLE users (id integer); CREATE TABLE users (id integer);", "CREATE FUNCTION f() RETURNS integer AS 'x';")


def test_defs_parser_handles_escaped_quotes_and_multiline_values():
    sql = """INSERT INTO defs (name,value) VALUES ('A','S''iptables''
p0
.') ;
INSERT INTO defs (name,value) VALUES ('B','I60
.') ;"""
    assert _defs_expected(sql) == {"A": "S'iptables'\np0\n.", "B": "I60\n."}


def test_all_preflight_seed_and_marker_queries_check_required_columns():
    available = {
        ("defs", "name"),
        ("ibs_states", "name"),
        ("admins", "admin_id"),
        ("admin_perms", "admin_id"),
    }
    assert not _has_required_columns(available, "defs", ["name", "value"])
    assert not _has_required_columns(available, "ibs_states", ["name", "value"])
    assert not _has_required_columns(available, "admins", ["admin_id", "username"])
    assert not _has_required_columns(available, "admin_perms", ["admin_id", "perm_name"])


def test_seed_queries_fail_closed_when_target_table_columns_are_missing():
    available = {("admins", "admin_id"), ("admins", "username"), ("admin_perms", "admin_id")}
    assert _has_required_columns(available, "admins", ["admin_id", "username"])
    assert not _has_required_columns(available, "admins", ["admin_id", "password"])
    assert not _has_required_columns(available, "admin_perms", ["admin_id", "perm_name"])
    assert not _has_required_columns(available, "missing_table", ["id"])


def test_canonical_archive_hash_is_pinned():
    assert re.fullmatch(r"[0-9a-f]{64}", CANONICAL_A124_SHA256)



def test_defs_parser_handles_legacy_backslash_escaped_quotes():
    sql = r"""INSERT INTO defs (name,value) VALUES ('BW_IPTABLES_COMMAND','S\'iptables\'
p0
.') ;"""
    assert _defs_expected(sql) == {"BW_IPTABLES_COMMAND": "S'iptables'\np0\n."}


def test_defs_parser_handles_full_native_shape():
    # Includes the two legacy SQL escape styles used by the A1.24 archive.
    sql = """INSERT INTO defs (name,value) VALUES ('A','S''iptables''\np0\n.') ;
INSERT INTO defs (name,value) VALUES ('B','S\\'tc\\'\np0\n.') ;"""
    assert _defs_expected(sql) == {"A": "S'iptables'\np0\n.", "B": "S'tc'\np0\n."}



def test_source_column_spec_covers_type_default_nullability_and_serial():
    assert _source_column_spec("integer primary key") == {
        "type": "integer", "nullable": False, "default": None, "serial": False
    }
    assert _source_column_spec("boolean DEFAULT 't'") == {
        "type": "boolean", "nullable": True, "default": "true", "serial": False
    }
    assert _source_column_spec("numeric(12,2) default 0") == {
        "type": "numeric(12,2)", "nullable": True, "default": "0", "serial": False
    }
    assert _source_column_spec("serial primary key") == {
        "type": "integer", "nullable": False, "default": None, "serial": True
    }
    assert _normalize_default("'t'::boolean") == "true"


def test_source_inventory_captures_table_level_primary_key():
    result = source_inventory(
        "CREATE TABLE composite (left_id integer, right_id integer, PRIMARY KEY (left_id, right_id));",
        "CREATE FUNCTION f() RETURNS integer AS 'x';",
    )
    assert result["column_specs"][("composite", "left_id")]["nullable"] is False
    assert result["column_specs"][("composite", "right_id")]["nullable"] is False



def test_function_signature_parser_handles_nested_types_and_overloads():
    functions = """
      CREATE OR REPLACE FUNCTION charge_user(bigint, numeric(12,2)) RETURNS integer AS 'x';
      CREATE FUNCTION charge_user(bigint, text[]) RETURNS integer AS 'x';
      CREATE FUNCTION report_user(timestamp without time zone, inet) RETURNS text AS 'x';
    """
    signatures = _function_signatures(functions)
    assert ("charge_user", ("bigint", "numeric(12,2)")) in signatures
    assert ("charge_user", ("bigint", "text[]")) in signatures
    assert ("report_user", ("timestamp without time zone", "inet")) in signatures



def test_source_rule_parser_extracts_native_protection_rules_and_detects_missing_source():
    source = """
      CREATE rule system_admin as on delete to admins where admin_id=0 do instead nothing;
      CREATE rule system_admin_god as on delete to admin_perms
        where admin_id=0 and perm_name='GOD' do instead nothing;
    """
    rules = _source_rules(source)
    assert rules["system_admin"] == {
        "event": "DELETE", "table": "admins", "condition": "admin_id=0",
        "action": "INSTEAD NOTHING",
    }
    assert rules["system_admin_god"]["table"] == "admin_perms"
    assert rules["system_admin_god"]["condition"] == "admin_id=0andperm_name='god'"
    with pytest.raises(ValueError, match="No supported source protection rules"):
        _source_rules("SELECT 1;")



def test_function_body_parser_decodes_postgres_quoted_literals_and_hashes_stably():
    functions = """
      CREATE OR REPLACE FUNCTION get_label(text) RETURNS text AS '
      BEGIN
        RETURN ''hello '' || $1;
      END;
      ' LANGUAGE plpgsql;
    """
    bodies = _function_definitions(functions)
    key = ("get_label", ("text",))
    assert "RETURN 'hello ' || $1;" in bodies[key]
    from hashlib import sha256
    assert len(sha256(bodies[key].encode("utf-8")).hexdigest()) == 64


def test_function_body_parser_fails_closed_on_missing_or_unterminated_body():
    with pytest.raises(ValueError, match="Missing quoted function body"):
        _function_definitions("CREATE FUNCTION f(integer) RETURNS integer;")
    with pytest.raises(ValueError, match="Unterminated quoted function body"):
        _function_definitions("CREATE FUNCTION f(integer) RETURNS integer AS 'BEGIN RETURN $1;")



def test_rule_condition_normalization_handles_catalog_parentheses_and_type_casts():
    assert _normalize_rule_condition("((admin_id = 0) AND (perm_name = 'GOD'::text))") == (
        "admin_id=0andperm_name='god'"
    )



def test_initial_state_parser_captures_every_canonical_state_seed():
    initial_sql = """
      INSERT INTO ibs_states VALUES ('MIDNIGHT_JOBS','0');
      INSERT INTO ibs_states VALUES ('LOWLOAD_JOBS','0');
      INSERT INTO ibs_states VALUES ('AUTO_CLEAN_CONNECTION_LOG','0');
      INSERT INTO ibs_states VALUES ('AUTO_CLEAN_CREDIT_CHANGE','0');
      INSERT INTO ibs_states VALUES ('AUTO_CLEAN_USER_AUDIT_LOG','0');
      INSERT INTO ibs_states VALUES ('AUTO_CLEAN_SNAPSHOTS','0');
      INSERT INTO ibs_states VALUES ('AUTO_CLEAN_WEB_ANALYZER_LOG','1209600'); -- days
    """
    states = _initial_state_expectations(initial_sql)
    assert len(states) == 7
    assert states["AUTO_CLEAN_WEB_ANALYZER_LOG"] == "1209600"
    with pytest.raises(ValueError, match="Duplicate initial IBS state"):
        _initial_state_expectations(
            "INSERT INTO ibs_states VALUES ('MIDNIGHT_JOBS','0'); "
            "INSERT INTO ibs_states VALUES ('MIDNIGHT_JOBS','1');"
        )



def test_initial_admin_and_god_permission_seeds_are_parsed_exactly():
    tables = """
      CREATE TABLE admins (
        admin_id integer primary key,
        username text unique,
        password char(34),
        deposit numeric(12,2) default 0,
        due numeric(12,2) default 0,
        name text,
        comment text,
        creator_id integer
      );
    """
    initial = """
      INSERT INTO admins VALUES (0,'system','',0,0,'IBS Internal System Account','',0);
      INSERT INTO admin_perms (admin_id,perm_name,perm_value) VALUES (0,'GOD','');
    """
    admin = _initial_admin_seed(initial, tables)
    assert admin["admin_id"] == 0
    assert admin["username"] == "system"
    assert admin["password"] == ""
    assert admin["deposit"] == 0
    assert admin["due"] == 0
    assert admin["name"] == "IBS Internal System Account"
    assert admin["comment"] == ""
    assert admin["creator_id"] == 0
    assert _initial_god_permission_seed(initial) == {
        "admin_id": 0, "perm_name": "GOD", "perm_value": ""
    }



def test_seed_comparison_accounts_for_postgresql_fixed_char_padding():
    spec = {"type": "character(34)"}
    assert _seed_values_equal("", " " * 34, spec)
    assert not _seed_values_equal("hash", "other", spec)
    assert not _seed_values_equal("", " " * 34, {"type": "text"})



def test_source_constraint_parser_tracks_primary_unique_foreign_key_and_check():
    schema = """
      CREATE TABLE parents (id integer primary key);
      CREATE TABLE children (
        id integer primary key,
        parent_id integer references parents,
        label text unique,
        quantity integer CHECK (quantity > 0)
      );
    """
    signatures = _source_constraint_signatures(schema)
    assert ("parents", "p", ("id",), None, (), None) in signatures
    assert ("children", "p", ("id",), None, (), None) in signatures
    assert ("children", "u", ("label",), None, (), None) in signatures
    assert ("children", "f", ("parent_id",), "parents", ("id",), None) in signatures
    assert ("children", "c", (), None, (), "quantity>0") in signatures



def test_check_expression_normalization_preserves_meaningful_grouping():
    assert _normalize_check_expression("(quantity > 0)") == "quantity>0"
    assert _normalize_check_expression("quantity > 0 AND (quantity < 99)") == (
        "quantity>0and(quantity<99)"
    )
    assert _normalize_check_expression("(quantity > 0 AND quantity < 99)") != (
        _normalize_check_expression("quantity > 0 OR quantity < 99")
    )



def test_source_index_details_captures_unique_partial_expression_and_key_count():
    indexes = _source_index_details("""
      CREATE UNIQUE INDEX users_name_idx ON users (username);
      CREATE INDEX users_active_idx ON users (active, user_id) WHERE active = true;
      CREATE INDEX users_lower_name_idx ON users ((lower(username)));
    """)
    assert indexes["users_name_idx"] == {
        "table": "users", "unique": True, "partial": False,
        "expression": False, "key_count": 1, "method": "btree",
        "expression_sql": "", "predicate_sql": "",
    }
    assert indexes["users_active_idx"] == {
        "table": "users", "unique": False, "partial": True,
        "expression": False, "key_count": 2, "method": "btree",
        "expression_sql": "", "predicate_sql": "active=true",
    }
    assert indexes["users_lower_name_idx"] == {
        "table": "users", "unique": False, "partial": False,
        "expression": True, "key_count": 1, "method": "btree",
        "expression_sql": "lower(username)", "predicate_sql": "",
    }



def test_index_sql_normalization_matches_cast_and_postgresql_any_rewrites():
    assert _normalize_index_sql("CAST(attr_value AS bigint)") == "attr_value"
    assert _normalize_index_sql("((attr_name = ANY (ARRAY['abs_exp_date'::text, 'first_login'::text])))") == (
        "attr_name=any(array['abs_exp_date','first_login'])"
    )
    assert _normalize_index_sql("attr_name IN ('abs_exp_date', 'first_login')") == (
        "attr_name=any(array['abs_exp_date','first_login'])"
    )



def test_source_index_inventory_normalizes_canonical_cast_and_partial_predicate():
    indexes = _source_index_details("""
      CREATE INDEX user_attrs_abs_exp_date
      ON user_attrs (attr_name, (cast(attr_value as bigint)))
      WHERE attr_name IN ('abs_exp_date', 'first_login');
    """)
    assert indexes["user_attrs_abs_exp_date"]["expression_sql"] == "attr_value"
    assert indexes["user_attrs_abs_exp_date"]["predicate_sql"] == (
        "attr_name=any(array['abs_exp_date','first_login'])"
    )


def test_native_table_trigger_drift_flags_only_triggers_on_a124_tables():
    triggers = [
        {"table": "users", "name": "audit_users", "definition": "CREATE TRIGGER audit_users ..."},
        {"table": "atd_radius_live_sessions", "name": "extension_trigger", "definition": "CREATE TRIGGER extension_trigger ..."},
    ]
    assert _native_table_trigger_drift({"users", "admins"}, triggers) == [
        {"table": "users", "name": "audit_users", "definition": "CREATE TRIGGER audit_users ..."}
    ]
    assert _native_table_trigger_drift({"users", "admins"}, []) == []


def test_source_sequence_specs_include_native_serial_and_explicit_sequence_defaults():
    specs = _source_sequence_specs(
        """
        CREATE SEQUENCE credit_change_id;
        CREATE TABLE sample (id serial PRIMARY KEY);
        """,
        {("sample", "id"): {"serial": True}},
    )
    assert specs["credit_change_id"] == {
        "start": 1, "minimum": 1, "maximum": 9223372036854775807,
        "increment": 1, "cycle": False, "cache": 1,
    }
    assert specs["sample_id_seq"] == {
        "start": 1, "minimum": 1, "maximum": 2147483647,
        "increment": 1, "cycle": False, "cache": 1,
    }


def test_sequence_definition_drift_reports_each_mismatched_setting():
    source = {
        "sample_id_seq": {
            "start": 1, "minimum": 1, "maximum": 2147483647,
            "increment": 1, "cycle": False, "cache": 1,
        }
    }
    target = [{
        "name": "sample_id_seq", "start": 1, "minimum": 1, "maximum": 999,
        "increment": 2, "cycle": False, "cache": 1, "last_value": 17,
    }]
    assert _sequence_definition_drift(source, target) == [
        {"sequence": "sample_id_seq", "field": "maximum", "source": 2147483647, "target": 999},
        {"sequence": "sample_id_seq", "field": "increment", "source": 1, "target": 2},
    ]
    assert _sequence_definition_drift(source, []) == []


def test_sequence_parser_fails_closed_on_nondefault_explicit_sequence_options():
    with pytest.raises(ValueError, match="Unsupported non-default canonical sequence"):
        _source_sequence_specs(
            "CREATE SEQUENCE custom_seq INCREMENT BY 2;",
            {},
        )
