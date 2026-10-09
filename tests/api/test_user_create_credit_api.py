from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.users as users_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class CreationConnection:
    def __init__(self, deposit="20.00"):
        self.deposit = Decimal(deposit)
        self.calls = []
        self.event_ids = iter((501, 502))
        self.commits = 0

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM admins" in sql and "FOR UPDATE" in sql:
            return Result((self.deposit,))
        if "UPDATE admins SET deposit" in sql:
            self.deposit = params[0]
        if "nextval('credit_change_id')" in sql:
            return Result((101,))
        if "nextval('ias_event_event_id')" in sql:
            return Result((next(self.event_ids),))
        return Result(None)

    def commit(self):
        self.commits += 1


def admin():
    return AdminPrincipal(
        admin_id=7,
        username="operator",
        remote_addr="192.0.2.20",
        permissions=AdminPermissionSet({"ADD NEW USER": ""}),
    )


def install_fakes(monkeypatch, conn):
    captured = {"create": None, "audit": []}

    class FakeGroupRepository:
        def __init__(self, _conn):
            pass

        def get(self, group_id):
            assert group_id == 2
            return SimpleNamespace(name="team", owner_id=7)

    class FakeUserRepository:
        def __init__(self, _conn):
            pass

        def create(self, username, status, *, owner_id, group_id, initial_credit):
            captured["create"] = {
                "username": username,
                "status": status,
                "owner_id": owner_id,
                "group_id": group_id,
                "initial_credit": initial_credit,
            }
            return SimpleNamespace(id=42, username=username)

        def set_status(self, user_id, status):
            captured["status"] = (user_id, status)

    class FakeAuditRepository:
        def __init__(self, _conn):
            pass

        def append(self, **kwargs):
            captured["audit"].append(kwargs)

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(users_api, "connection", fake_connection)
    monkeypatch.setattr(users_api, "GroupRepository", FakeGroupRepository)
    monkeypatch.setattr(users_api, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(users_api, "OperationalAuditRepository", FakeAuditRepository)
    return captured


def test_user_creation_initial_credit_debits_deposit_and_writes_source_logs(monkeypatch):
    conn = CreationConnection()
    captured = install_fakes(monkeypatch, conn)

    result = users_api.create_user(
        users_api.UserCreate(
            username=" alice ",
            group_id=2,
            initial_credit=Decimal("10.00"),
            credit_comment="welcome credit",
        ),
        admin(),
    )

    assert (result.id, result.username) == (42, "alice")
    assert captured["create"]["initial_credit"] == Decimal("10.00")
    assert conn.deposit == Decimal("10.00")
    assert conn.commits == 1
    credit_log = next(params for sql, params in conn.calls if "INSERT INTO credit_change" in sql)
    assert credit_log == (101, 7, Decimal("10.00"), Decimal("10.00"), "192.0.2.20", "welcome credit")
    ias_logs = [params for sql, params in conn.calls if "INSERT INTO ias_event" in sql]
    assert ias_logs == [
        (501, 3, "operator", Decimal("0.00"), "42", ""),
        (502, 1, "operator", Decimal("10.00"), "42", ""),
    ]
    assert captured["audit"][0]["details"]["initial_credit"] == "10.00"


def test_user_creation_rejects_insufficient_deposit_without_commit_or_audit(monkeypatch):
    conn = CreationConnection(deposit="5.00")
    captured = install_fakes(monkeypatch, conn)

    with pytest.raises(HTTPException) as denied:
        users_api.create_user(
            users_api.UserCreate(username="alice", group_id=2, initial_credit=Decimal("10.00")),
            admin(),
        )

    assert denied.value.status_code == 403
    assert conn.commits == 0
    assert captured["audit"] == []
    assert not any("INSERT INTO credit_change" in sql for sql, _ in conn.calls)
