from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

import atd_radius.api.admin_deposits as deposits_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.calls = []
        self.deposit = Decimal("20.00")
        self.commits = 0

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT value FROM defs WHERE name = %s" in sql:
            return Result(("I1\n.",))
        if "FROM admins" in sql and "FOR UPDATE" in sql:
            return Result((8, "target-admin", self.deposit))
        if "nextval('admin_deposit_change_id')" in sql:
            return Result((31,))
        if "nextval('ias_event_event_id')" in sql:
            return Result((41,))
        if "UPDATE admins SET deposit = deposit +" in sql:
            self.deposit += params[0]
        if "INSERT INTO operational_audit_events" in sql:
            return Result((99, datetime(2026, 10, 10, tzinfo=timezone.utc)))
        return Result(None)

    def commit(self):
        self.commits += 1


def principal(perms=None, remote_addr="192.0.2.20"):
    return AdminPrincipal(7, "operator", remote_addr, AdminPermissionSet(perms or {}))


def install_connection(monkeypatch, conn):
    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(deposits_api, "connection", fake_connection)


def test_admin_deposit_endpoint_updates_native_balance_logs_and_audit(monkeypatch):
    conn = Connection()
    install_connection(monkeypatch, conn)
    admin = principal({"SEE ADMIN INFO": "", "CHANGE ADMIN INFO": "", "CHANGE ADMIN DEPOSIT": ""})

    result = deposits_api.change_admin_deposit(
        "target-admin",
        deposits_api.AdminDepositChange(delta=Decimal("5.50"), comment="funding"),
        admin,
    )

    assert result.admin_id == 8
    assert result.deposit == Decimal("25.50")
    assert conn.commits == 1
    assert any("INSERT INTO admin_deposit_change" in sql for sql, _ in conn.calls)
    assert any("INSERT INTO ias_event" in sql for sql, _ in conn.calls)
    assert any("INSERT INTO operational_audit_events" in sql for sql, _ in conn.calls)


def test_admin_deposit_permission_requires_source_dependencies():
    from atd_radius.api.admin_dependencies import require_admin_permission

    dependency = require_admin_permission("CHANGE ADMIN DEPOSIT")
    with pytest.raises(HTTPException) as denied:
        dependency(principal({"CHANGE ADMIN DEPOSIT": ""}))

    assert denied.value.status_code == 403

    allowed = dependency(
        principal({
            "SEE ADMIN INFO": "",
            "CHANGE ADMIN INFO": "",
            "CHANGE ADMIN DEPOSIT": "",
        })
    )
    assert allowed.admin_id == 7
