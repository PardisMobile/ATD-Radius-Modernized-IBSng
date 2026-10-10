from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.admins as admins_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.admin_deletion import AdminDeletionError


def principal(perms=None):
    return AdminPrincipal(7, "operator", "192.0.2.20", AdminPermissionSet(perms or {}))


def test_admin_delete_commits_and_audits(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)
    captured = {}

    class Repo:
        def __init__(self, _conn):
            pass

        def delete(self, username, *, deleter_username):
            captured["delete"] = (username, deleter_username)
            return SimpleNamespace(admin_id=8, username=username, deposit="12.50")

    class Audit:
        def __init__(self, _conn):
            pass

        def append(self, **kwargs):
            captured["audit"] = kwargs

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminDeletionRepository", Repo)
    monkeypatch.setattr(admins_api, "OperationalAuditRepository", Audit)
    response = admins_api.delete_admin("target", principal({"DELETE ADMIN": "", "SEE ADMIN INFO": ""}))
    assert response.status_code == 204
    assert captured["delete"] == ("target", "operator")
    assert captured["audit"]["action"] == "admin.delete"
    assert captured["audit"]["target_id"] == "8"
    assert conn.commits == 1


def test_admin_delete_maps_system_account_protection(monkeypatch):
    @contextmanager
    def fake_connection():
        yield object()

    class Repo:
        def __init__(self, _conn):
            pass

        def delete(self, *_args, **_kwargs):
            raise AdminDeletionError("system_admin_protected")

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminDeletionRepository", Repo)
    with pytest.raises(HTTPException) as error:
        admins_api.delete_admin("system", principal({"DELETE ADMIN": "", "SEE ADMIN INFO": ""}))
    assert error.value.status_code == 409
