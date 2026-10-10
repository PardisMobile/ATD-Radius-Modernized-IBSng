from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

import atd_radius.api.users as users_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.api.users import UserCreditChange
from atd_radius.domain.admin_permissions import AdminPermissionSet


class Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = list(rows) if rows is not None else ([row] if row is not None else [])

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class CreditAPIFakeConnection:
    def __init__(self, *, owner_id=7, credit="25.00", deposit="100.00"):
        self.owner_id = owner_id
        self.credit = Decimal(credit)
        self.deposit = Decimal(deposit)
        self.user_rows = [(42, "alice", owner_id, self.credit)]
        self.calls = []
        self.commits = 0

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT value FROM defs WHERE name = %s" in sql:
            return Result(("I1\n.",))
        if "FOR UPDATE OF u" in sql:
            return Result(self.user_rows[0] if self.user_rows else None, self.user_rows)
        if "FROM admins" in sql and "FOR UPDATE" in sql:
            return Result((self.deposit,))
        if "nextval('credit_change_id')" in sql:
            return Result((101,))
        if "nextval('ias_event_event_id')" in sql:
            return Result((501,))
        if "INSERT INTO operational_audit_events" in sql:
            return Result((999, datetime(2026, 10, 10, tzinfo=timezone.utc)))
        return Result(None)

    def commit(self):
        self.commits += 1


def principal(permissions):
    return AdminPrincipal(
        admin_id=7,
        username="operator",
        remote_addr="192.0.2.20",
        permissions=AdminPermissionSet(permissions),
    )


def install_connection(monkeypatch, conn):
    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(users_api, "connection", fake_connection)


def test_credit_endpoint_commits_native_and_operational_audit_together(monkeypatch):
    conn = CreditAPIFakeConnection()
    install_connection(monkeypatch, conn)
    admin = principal({
        "GET USER INFORMATION": "All",
        "CHANGE USER CREDIT": "All",
    })

    result = users_api.change_user_credit(
        "alice",
        UserCreditChange(delta=Decimal("12.50"), comment="top-up"),
        admin,
    )

    assert result.user_id == 42
    assert result.credit == Decimal("37.50")
    assert conn.commits == 1
    assert any("INSERT INTO credit_change" in sql for sql, _ in conn.calls)
    assert any("INSERT INTO credit_change_userid" in sql for sql, _ in conn.calls)
    assert any("INSERT INTO ias_event" in sql for sql, _ in conn.calls)
    assert any("INSERT INTO operational_audit_events" in sql for sql, _ in conn.calls)


def test_credit_endpoint_denies_restricted_admin_for_another_owners_user(monkeypatch):
    conn = CreditAPIFakeConnection(owner_id=8)
    install_connection(monkeypatch, conn)
    admin = principal({
        "GET USER INFORMATION": "Restricted",
        "CHANGE USER CREDIT": "Restricted",
    })

    with pytest.raises(HTTPException) as denied:
        users_api.change_user_credit(
            "alice",
            UserCreditChange(delta=Decimal("1.00"), comment="top-up"),
            admin,
        )

    assert denied.value.status_code == 403
    assert conn.commits == 0
    assert not any("FROM admins" in sql for sql, _ in conn.calls)

def test_bulk_credit_endpoint_checks_each_owner_and_commits_batch_once(monkeypatch):
    conn = CreditAPIFakeConnection()
    conn.user_rows = [
        (42, "alice", 7, Decimal("25.00")),
        (43, "bob", 7, Decimal("10.00")),
    ]
    install_connection(monkeypatch, conn)
    admin = principal({
        "GET USER INFORMATION": "Restricted",
        "CHANGE USER CREDIT": "Restricted",
    })

    result = users_api.change_users_credit_bulk(
        users_api.UserCreditBulkChange(
            usernames=["bob", "alice"],
            delta=Decimal("2.00"),
            comment="batch top-up",
        ),
        admin,
    )

    assert [item.user_id for item in result.items] == [42, 43]
    assert [item.credit for item in result.items] == [Decimal("27.00"), Decimal("12.00")]
    assert result.total_admin_credit == Decimal("4.00")
    assert conn.commits == 1
    credit_log = next(params for sql, params in conn.calls if "INSERT INTO credit_change" in sql)
    assert credit_log[3] == Decimal("4.00")


def test_bulk_credit_endpoint_rejects_batch_if_any_user_is_out_of_scope(monkeypatch):
    conn = CreditAPIFakeConnection()
    conn.user_rows = [
        (42, "alice", 7, Decimal("25.00")),
        (43, "bob", 8, Decimal("10.00")),
    ]
    install_connection(monkeypatch, conn)
    admin = principal({
        "GET USER INFORMATION": "Restricted",
        "CHANGE USER CREDIT": "Restricted",
    })

    with pytest.raises(HTTPException) as denied:
        users_api.change_users_credit_bulk(
            users_api.UserCreditBulkChange(
                usernames=["alice", "bob"],
                delta=Decimal("1.00"),
                comment="batch top-up",
            ),
            admin,
        )

    assert denied.value.status_code == 403
    assert conn.commits == 0
    assert not any("FROM admins" in sql for sql, _ in conn.calls)

