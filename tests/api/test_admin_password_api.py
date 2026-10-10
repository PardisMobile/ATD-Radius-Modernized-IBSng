from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.admins as admins_api
from atd_radius.api.admin_dependencies import AdminPrincipal, can_change_admin_password
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.domain.ibsng_password import verify_ibsng_password


def principal(username="operator", perms=None):
    return AdminPrincipal(7, username, "192.0.2.20", AdminPermissionSet(perms or {}))


def test_self_password_change_does_not_require_change_admin_password():
    assert can_change_admin_password(principal("operator", {}), "operator")
    assert not can_change_admin_password(principal("operator", {}), "another")
    assert can_change_admin_password(
        principal("operator", {"SEE ADMIN INFO": "", "CHANGE ADMIN PASSWORD": ""}),
        "another",
    )


def test_change_admin_password_hashes_source_format_and_audits_without_leaking_hash(monkeypatch):
    conn = type("Conn", (), {"commits": 0, "commit": lambda self: setattr(self, "commits", self.commits + 1)})()
    captured = {}
    class Repo:
        def __init__(self, _conn): pass
        def update_password(self, username, password_hash):
            captured["username"] = username
            captured["hash"] = password_hash
            return SimpleNamespace(admin_id=7, username=username)
    class Audit:
        def __init__(self, _conn): pass
        def append(self, **kwargs):
            captured["audit"] = kwargs
    @contextmanager
    def fake_connection():
        yield conn
    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminCredentialRepository", Repo)
    monkeypatch.setattr(admins_api, "OperationalAuditRepository", Audit)
    response = admins_api.change_admin_password(
        "operator", admins_api.AdminPasswordChange(new_password=" new-pass_123 "),
        principal("operator", {}),
    )
    assert response.status_code == 204
    assert captured["username"] == "operator"
    assert captured["hash"].startswith("$1$")
    assert verify_ibsng_password("new-pass_123", captured["hash"])
    assert captured["audit"]["details"] == {"target_username": "operator", "self_change": True}
    assert captured["hash"] not in str(captured["audit"])
    assert conn.commits == 1


def test_change_other_admin_password_requires_native_permission_chain(monkeypatch):
    with pytest.raises(HTTPException) as denied:
        admins_api.change_admin_password(
            "another", admins_api.AdminPasswordChange(new_password="new-pass"),
            principal("operator", {}),
        )
    assert denied.value.status_code == 403


def test_change_admin_password_rejects_source_invalid_characters_before_db(monkeypatch):
    @contextmanager
    def fake_connection():
        raise AssertionError("invalid password must not open a transaction")
        yield
    monkeypatch.setattr(admins_api, "connection", fake_connection)
    with pytest.raises(HTTPException) as denied:
        admins_api.change_admin_password(
            "operator", admins_api.AdminPasswordChange(new_password="bad password"),
            principal("operator", {}),
        )
    assert denied.value.status_code == 422



def test_admin_permission_view_returns_native_permission_values(monkeypatch):
    from atd_radius.domain.admin_permissions import AdminPermissionSet

    captured = {}

    class Repo:
        def __init__(self, _conn):
            pass

        def get_permissions(self, username):
            captured["username"] = username
            return (("GOD", None), ("GROUP ACCESS", "Office,VPN"))

    @contextmanager
    def fake_connection():
        yield object()

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminInformationRepository", Repo)
    response = admins_api.get_admin_permissions(
        "target",
        principal("operator", {"SEE ADMIN INFO": "", "SEE ADMIN PERMISSIONS": ""}),
    )
    assert captured["username"] == "target"
    assert [item.model_dump() for item in response] == [
        {"name": "GOD", "value": None},
        {"name": "GROUP ACCESS", "value": "Office,VPN"},
    ]


def test_admin_permission_view_returns_not_found_for_unknown_admin(monkeypatch):
    @contextmanager
    def fake_connection():
        yield object()

    class Repo:
        def __init__(self, _conn):
            pass

        def get_permissions(self, _username):
            return None

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminInformationRepository", Repo)
    with pytest.raises(HTTPException) as missing:
        admins_api.get_admin_permissions(
            "missing",
            principal("operator", {"SEE ADMIN INFO": "", "SEE ADMIN PERMISSIONS": ""}),
        )
    assert missing.value.status_code == 404



def test_admin_permission_view_requires_see_admin_info_dependency():
    from atd_radius.api.admin_dependencies import require_admin_permission

    guard = require_admin_permission("SEE ADMIN PERMISSIONS")
    with pytest.raises(HTTPException) as denied:
        guard(principal=principal("operator", {"SEE ADMIN PERMISSIONS": ""}))
    assert denied.value.status_code == 403
    allowed = guard(
        principal=principal("operator", {"SEE ADMIN INFO": "", "SEE ADMIN PERMISSIONS": ""})
    )
    assert allowed.username == "operator"
