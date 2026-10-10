from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.admins as admins_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.admin_permission_mutations import AdminPermissionMutationError


def principal(perms=None):
    return AdminPrincipal(7, "operator", "192.0.2.20", AdminPermissionSet(perms or {}))


def test_permission_mutation_endpoint_commits_and_audits(monkeypatch):
    conn = SimpleNamespace(commits=0, commit=lambda: None)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)
    captured = {}

    class Repo:
        def __init__(self, _conn):
            pass

        def add_or_change(self, username, permission_name, value):
            captured["mutation"] = (username, permission_name, value)
            return SimpleNamespace(admin_id=8, username=username, permissions=(("GET USER INFORMATION", "All"),))

    class Audit:
        def __init__(self, _conn):
            pass

        def append(self, **kwargs):
            captured["audit"] = kwargs

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminPermissionMutationRepository", Repo)
    monkeypatch.setattr(admins_api, "OperationalAuditRepository", Audit)
    result = admins_api.add_or_change_admin_permission(
        "target", "GET USER INFORMATION", admins_api.AdminPermissionMutation(value="All"),
        principal({"CHANGE ADMIN PERMISSIONS": "", "SEE ADMIN INFO": "", "SEE ADMIN PERMISSIONS": ""}),
    )
    assert [(item.name, item.value) for item in result] == [("GET USER INFORMATION", "All")]
    assert captured["mutation"] == ("target", "GET USER INFORMATION", "All")
    assert captured["audit"]["action"] == "admin.permission.change"
    assert captured["audit"]["target_id"] == "8"
    assert conn.commits == 1


def test_permission_mutation_maps_dependency_failure(monkeypatch):
    @contextmanager
    def fake_connection():
        yield object()

    class Repo:
        def __init__(self, _conn):
            pass

        def add_or_change(self, *_args):
            raise AdminPermissionMutationError("dependency_not_satisfied")

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminPermissionMutationRepository", Repo)
    with pytest.raises(HTTPException) as error:
        admins_api.add_or_change_admin_permission(
            "target", "CHANGE ADMIN INFO", admins_api.AdminPermissionMutation(value=""),
            principal({"CHANGE ADMIN PERMISSIONS": "", "SEE ADMIN INFO": "", "SEE ADMIN PERMISSIONS": ""}),
        )
    assert error.value.status_code == 409


def test_permission_delete_value_endpoint_uses_scoped_operation(monkeypatch):
    captured = {}

    class Repo:
        def __init__(self, _conn):
            pass

        def delete_multi_value(self, username, permission_name, value):
            captured["args"] = (username, permission_name, value)
            return SimpleNamespace(admin_id=8, username=username, permissions=(("GROUP ACCESS", "sales"),))

    class Audit:
        def __init__(self, _conn):
            pass

        def append(self, **kwargs):
            captured["audit"] = kwargs

    @contextmanager
    def fake_connection():
        yield SimpleNamespace(commit=lambda: None)

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminPermissionMutationRepository", Repo)
    monkeypatch.setattr(admins_api, "OperationalAuditRepository", Audit)
    result = admins_api.delete_admin_permission_value(
        "target", "GROUP ACCESS", "staff",
        principal({"CHANGE ADMIN PERMISSIONS": "", "SEE ADMIN INFO": "", "SEE ADMIN PERMISSIONS": ""}),
    )
    assert captured["args"] == ("target", "GROUP ACCESS", "staff")
    assert captured["audit"]["action"] == "admin.permission.delete_value"
    assert result[0].value == "sales"
