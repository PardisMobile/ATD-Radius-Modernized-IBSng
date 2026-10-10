from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.users as users_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.user_attribute_mutations import MutatedUserAttributes


def principal(perms):
    return AdminPrincipal(7, "operator", "192.0.2.20", AdminPermissionSet(perms))


def install_connection(monkeypatch, conn):
    @contextmanager
    def fake_connection():
        yield conn
    monkeypatch.setattr(users_api, "connection", fake_connection)


def test_attribute_mutation_requires_change_permission_and_commits_audit(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)
    captured = {}

    class Repository:
        def __init__(self, _conn):
            pass
        def lock_target(self, username):
            assert username == "alice"
            return SimpleNamespace(user_id=42, username="alice", owner_id=7)
        def apply(self, target, **kwargs):
            captured["apply"] = kwargs
            return MutatedUserAttributes(target.user_id, target.username, [("comment", "VIP")])

    class Audit:
        def __init__(self, _conn):
            pass
        def append(self, **kwargs):
            captured["audit"] = kwargs

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "UserAttributeMutationRepository", Repository)
    monkeypatch.setattr(users_api, "OperationalAuditRepository", Audit)

    result = users_api.mutate_user_attributes(
        "alice",
        users_api.UserAttributeMutation(attrs={"comment": "VIP"}),
        principal({"GET USER INFORMATION": "All", "CHANGE USER ATTRIBUTES": "All"}),
    )

    assert result.id == 42
    assert result.attributes[0].value == "VIP"
    assert captured["apply"]["admin_id"] == 7
    assert captured["audit"]["action"] == "user.attributes.mutate"
    assert captured["audit"]["details"]["changed_attributes"] == ["comment"]
    assert conn.commits == 1


def test_attribute_mutation_denies_restricted_admin_for_other_owner(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)

    class Repository:
        def __init__(self, _conn):
            pass
        def lock_target(self, _username):
            return SimpleNamespace(user_id=42, username="alice", owner_id=8)

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "UserAttributeMutationRepository", Repository)

    with pytest.raises(HTTPException) as error:
        users_api.mutate_user_attributes(
            "alice",
            users_api.UserAttributeMutation(attrs={"name": "Alice"}),
            principal({"GET USER INFORMATION": "Restricted", "CHANGE USER ATTRIBUTES": "Restricted"}),
        )

    assert error.value.status_code == 403
    assert conn.commits == 0


def test_attribute_mutation_returns_not_found_for_missing_user(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)

    class Repository:
        def __init__(self, _conn):
            pass
        def lock_target(self, _username):
            return None

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "UserAttributeMutationRepository", Repository)

    with pytest.raises(HTTPException) as error:
        users_api.mutate_user_attributes(
            "missing",
            users_api.UserAttributeMutation(attrs={"comment": "x"}),
            principal({"GET USER INFORMATION": "All", "CHANGE USER ATTRIBUTES": "All"}),
        )

    assert error.value.status_code == 404
    assert conn.commits == 0
