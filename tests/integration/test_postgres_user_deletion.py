"""PostgreSQL safety tests for native A1.24 user deletion.

These tests use an isolated schema in ATD_TEST_DATABASE_URL and never touch
application tables in the configured database.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest

from atd_radius.infrastructure.user_deletion import UserDeletionOnlineError, UserDeletionRepository

_DSN = os.getenv("ATD_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not _DSN, reason="ATD_TEST_DATABASE_URL is not configured")


@contextmanager
def _isolated_schema():
    schema = f"test_user_delete_{uuid4().hex}"
    with psycopg.connect(_DSN, autocommit=True) as admin_conn:
        admin_conn.execute(f'CREATE SCHEMA "{schema}"')
        try:
            with psycopg.connect(_DSN) as conn:
                conn.execute(f'SET search_path TO "{schema}"')
                _create_schema(conn)
                conn.commit()
                yield conn
        finally:
            admin_conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def _create_schema(conn):
    ddl = """
        CREATE TABLE admins (admin_id integer PRIMARY KEY, deposit numeric(12,2) NOT NULL);
        CREATE TABLE users (user_id bigint PRIMARY KEY, owner_id integer, credit numeric(12,2));
        CREATE TABLE normal_users (user_id bigint, normal_username text);
        CREATE TABLE user_attrs (user_id bigint, attr_name text, attr_value text);
        CREATE TABLE atd_radius_live_sessions (user_id bigint, state jsonb);
        CREATE TABLE atd_radius_login_reservations (user_id bigint);
        CREATE TABLE connection_log (
            connection_log_id bigint PRIMARY KEY, user_id bigint, logout_time timestamp, successful boolean
        );
        CREATE TABLE connection_log_details (connection_log_id bigint, name text, value text);
        CREATE TABLE persistent_lan_users (user_id bigint);
        CREATE TABLE caller_id_users (user_id bigint, caller_id text);
        CREATE TABLE voip_users (user_id bigint, voip_username text);
        CREATE TABLE user_messages (user_id bigint);
        CREATE TABLE admin_messages (user_id bigint);
        CREATE TABLE web_analyzer_log (user_id bigint);
        CREATE TABLE internet_bw_snapshot (user_id bigint);
        CREATE TABLE user_audit_log (is_user text, object_id bigint);
        CREATE TABLE defs (name text PRIMARY KEY, value text);
        CREATE SEQUENCE credit_change_id;
        CREATE TABLE credit_change (
            credit_change_id bigint PRIMARY KEY, admin_id integer, action smallint,
            per_user_credit numeric(12,2), admin_credit numeric(12,2), remote_addr inet, comment text
        );
        CREATE TABLE credit_change_userid (credit_change_id bigint, user_id bigint);
        CREATE SEQUENCE ias_event_event_id;
        CREATE TABLE ias_event (
            event_id bigint PRIMARY KEY, event_type smallint, actor text,
            amount numeric(12,2), destinations text, comment text
        );
    """
    for statement in ddl.split(";"):
        if statement.strip():
            conn.execute(statement)


def _seed_users(conn, ias_enabled="I1\n."):
    conn.execute("INSERT INTO admins VALUES (8, 10.00)")
    conn.execute("INSERT INTO users VALUES (1, 8, 4.25), (2, 8, -3.00)")
    conn.execute("INSERT INTO normal_users VALUES (1, 'alice')")
    conn.execute("INSERT INTO user_attrs VALUES (1, 'mail_quota', '100')")
    conn.execute("INSERT INTO defs VALUES ('IAS_ENABLED', %s)", (ias_enabled,))


@pytest.mark.parametrize(("ias_enabled", "expected_events"), [("I1\n.", 1), ("I0\n.", 0)])
def test_postgres_delete_refund_history_and_ias_are_transactional(ias_enabled, expected_events):
    with _isolated_schema() as conn:
        _seed_users(conn, ias_enabled)
        result = UserDeletionRepository(conn).delete(
            [2, 1], admin_id=8, admin_username="admin", remote_addr="192.0.2.10",
            comment="cleanup", delete_connection_logs=False, delete_audit_logs=False,
        )
        assert result.refunded_credit == 4.25
        assert [target.user_id for target in result.targets] == [1, 2]
        conn.commit()

        assert conn.execute("SELECT deposit FROM admins WHERE admin_id=8").fetchone()[0] == 14.25
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM credit_change").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM credit_change_userid").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM ias_event").fetchone()[0] == expected_events
        assert conn.execute("SELECT count(*) FROM user_audit_log").fetchone()[0] == 0


@pytest.mark.parametrize("online_source", ["durable_session", "login_reservation", "open_connection_log"])
def test_postgres_delete_fails_closed_for_each_online_state_source(online_source):
    with _isolated_schema() as conn:
        _seed_users(conn)
        if online_source == "durable_session":
            conn.execute(
                "INSERT INTO atd_radius_live_sessions VALUES (1, %s::jsonb)",
                ('{"started":true,"stopped":false}',),
            )
        elif online_source == "login_reservation":
            conn.execute("INSERT INTO atd_radius_login_reservations VALUES (1)")
        else:
            conn.execute("INSERT INTO connection_log VALUES (1, 1, NULL, TRUE)")
        conn.commit()

        with pytest.raises(UserDeletionOnlineError):
            UserDeletionRepository(conn).delete(
                [1], admin_id=8, admin_username="admin", remote_addr="192.0.2.10",
                comment="must not delete online", delete_connection_logs=True, delete_audit_logs=True,
            )
        conn.rollback()
        assert conn.execute("SELECT count(*) FROM users WHERE user_id=1").fetchone()[0] == 1
        assert conn.execute("SELECT deposit FROM admins WHERE admin_id=8").fetchone()[0] == 10.00
        assert conn.execute("SELECT count(*) FROM credit_change").fetchone()[0] == 0


def test_postgres_delete_rolls_back_refund_and_ledgers_on_late_failure():
    with _isolated_schema() as conn:
        _seed_users(conn)
        conn.execute("""
            CREATE FUNCTION reject_user_delete() RETURNS trigger LANGUAGE plpgsql AS $
            BEGIN
                RAISE EXCEPTION 'injected user deletion failure';
            END;
            $
        """)
        conn.execute("""
            CREATE TRIGGER reject_user_delete BEFORE DELETE ON users
            FOR EACH ROW EXECUTE FUNCTION reject_user_delete()
        """)
        conn.commit()

        with pytest.raises(psycopg.Error, match="injected user deletion failure"):
            UserDeletionRepository(conn).delete(
                [1], admin_id=8, admin_username="admin", remote_addr="192.0.2.10",
                comment="rollback test", delete_connection_logs=False, delete_audit_logs=False,
            )
        conn.rollback()
        assert conn.execute("SELECT count(*) FROM users WHERE user_id=1").fetchone()[0] == 1
        assert conn.execute("SELECT deposit FROM admins WHERE admin_id=8").fetchone()[0] == 10.00
        assert conn.execute("SELECT count(*) FROM credit_change").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM ias_event").fetchone()[0] == 0
