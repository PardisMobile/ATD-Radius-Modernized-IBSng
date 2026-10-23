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
