from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.users as users_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet


def principal(perms, remote_addr="192.0.2.20"):
    return AdminPrincipal(7, "operator", remote_addr, AdminPermissionSet(perms))


def install_connection(monkeypatch, conn):
    @contextmanager
    def fake_connection():
        yield conn
    monkeypatch.setattr(users_api, "connection", fake_connection)


def test_fast_dial_read_checks_owner_scope_and_returns_destination(monkeypatch):
    conn = SimpleNamespace()
    target = SimpleNamespace(user_id=42, voip_username="alice-voip", owner_id=7)

    class Repository:
        def __init__(self, _conn): pass
        def get_target(self, username):
            assert username == "alice-voip"
            return target
        def get_destination(self, user_id, index):
            assert (user_id, index) == (42, 3)
            return "123456"

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "FastDialActionsRepository", Repository)
    result = users_api.get_fast_dial_destination(
        "alice-voip", 3, principal({"GET USER INFORMATION": "All"})
    )
    assert result.destination == "123456"
    assert result.index == 3


def test_fast_dial_write_requires_voip_permission_and_records_operational_audit(monkeypatch):
    conn = SimpleNamespace(committed=False)
    conn.commit = lambda: setattr(conn, "committed", True)
    captured = {}
    target = SimpleNamespace(user_id=42, voip_username="alice-voip", owner_id=7)

    class Repository:
        def __init__(self, _conn): pass
        def lock_target(self, username):
            assert username == "alice-voip"
            return target
        def set_destination(self, user_id, index, destination):
            captured["write"] = (user_id, index, destination)
            return destination

    class Audit:
        def __init__(self, _conn): pass
        def append(self, **kwargs): captured["audit"] = kwargs

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "FastDialActionsRepository", Repository)
    monkeypatch.setattr(users_api, "OperationalAuditRepository", Audit)
    result = users_api.set_fast_dial_destination(
        "alice-voip",
        3,
        users_api.FastDialDestinationChange(destination="123456"),
        principal({
            "GET USER INFORMATION": "All",
            "CHANGE USER ATTRIBUTES": "All",
            "CHANGE VOIP USER ATTRIBUTES": "All",
        }),
    )
    assert result.destination == "123456"
    assert captured["write"] == (42, 3, "123456")
    assert captured["audit"]["action"] == "user.fast_dial.destination.set"
    assert captured["audit"]["details"]["index"] == 3
    assert conn.committed is True


def test_fast_dial_write_denies_admin_without_voip_attribute_permission(monkeypatch):
    conn = SimpleNamespace(committed=False)
    conn.commit = lambda: setattr(conn, "committed", True)
    target = SimpleNamespace(user_id=42, voip_username="alice-voip", owner_id=7)

    class Repository:
        def __init__(self, _conn): pass
        def lock_target(self, _username): return target

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "FastDialActionsRepository", Repository)
    with pytest.raises(HTTPException) as error:
        users_api.set_fast_dial_destination(
            "alice-voip",
            3,
            users_api.FastDialDestinationChange(destination="123456"),
            principal({
                "GET USER INFORMATION": "All",
                "CHANGE USER ATTRIBUTES": "All",
            }),
        )
    assert error.value.status_code == 403
    assert conn.committed is False
