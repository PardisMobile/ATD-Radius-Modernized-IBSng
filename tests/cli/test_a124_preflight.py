from __future__ import annotations

import re
from pathlib import Path

import pytest

from atd_radius.cli.a124_preflight import (
    CANONICAL_A124_SHA256,
    _defs_expected,
    _split_top_level,
    _table_bodies,
    source_inventory,
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
