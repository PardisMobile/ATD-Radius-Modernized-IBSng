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
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class CreditAPIFakeConnection:
    def __init__(self, *, owner_id=7, credit="25.00", deposit="100.00"):
        self.owner_id = owner_id
        self.credit = Decimal(credit)
        self.deposit = Decimal(deposit)
        self.calls = []
        self.commits = 0

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FOR UPDATE OF u" in sql:
            return Result((42, "alice", self.owner_id, self.credit))
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
