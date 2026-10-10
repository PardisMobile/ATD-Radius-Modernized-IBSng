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


def test_owner_transfer_to_self_does_not_require_change_users_owner(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)
    captured = {}

    class Repository:
        def __init__(self, _conn):
            pass
        def lock_target(self, _username):
            return SimpleNamespace(
                user_id=42, username="alice", owner_id=8, owner_username="previous"
            )
        def change_owner(self, target, **kwargs):
            captured["change"] = kwargs
            return "operator"

    class Audit:
        def __init__(self, _conn):
            pass
        def append(self, **kwargs):
            captured["audit"] = kwargs

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "UserAttributeMutationRepository", Repository)
    monkeypatch.setattr(users_api, "OperationalAuditRepository", Audit)

    result = users_api.change_user_owner(
        "alice",
        users_api.UserOwnerChange(owner_username="operator"),
        principal({"GET USER INFORMATION": "All", "CHANGE USER ATTRIBUTES": "All"}),
    )

    assert result.owner_username == "operator"
    assert captured["change"]["owner_username"] == "operator"
    assert captured["audit"]["action"] == "user.owner.change"
    assert captured["audit"]["details"] == {
        "previous_owner": "previous",
        "new_owner": "operator",
    }
    assert conn.commits == 1


def test_owner_transfer_to_another_admin_requires_change_users_owner(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)
    called = {"change": False}

    class Repository:
        def __init__(self, _conn):
            pass
        def lock_target(self, _username):
            return SimpleNamespace(
                user_id=42, username="alice", owner_id=7, owner_username="operator"
            )
        def change_owner(self, _target, **_kwargs):
            called["change"] = True
            return "other"

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "UserAttributeMutationRepository", Repository)

    with pytest.raises(HTTPException) as error:
        users_api.change_user_owner(
            "alice",
            users_api.UserOwnerChange(owner_username="other"),
            principal({"GET USER INFORMATION": "All", "CHANGE USER ATTRIBUTES": "All"}),
        )

    assert error.value.status_code == 403
    assert called["change"] is False
    assert conn.commits == 0



def test_owner_transfer_maps_missing_owner_to_not_found(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)

    class Repository:
        def __init__(self, _conn):
            pass
        def lock_target(self, _username):
            return SimpleNamespace(
                user_id=42, username="alice", owner_id=7, owner_username="operator"
            )
        def change_owner(self, _target, **_kwargs):
            raise LookupError("owner administrator not found")

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "UserAttributeMutationRepository", Repository)

    with pytest.raises(HTTPException) as error:
        users_api.change_user_owner(
            "alice",
            users_api.UserOwnerChange(owner_username="missing"),
            principal({
                "GET USER INFORMATION": "All",
                "CHANGE USER ATTRIBUTES": "All",
                "CHANGE USERS OWNER": "",
            }),
        )

    assert error.value.status_code == 404
    assert conn.commits == 0



def test_group_change_checks_group_access_and_commits_both_audits(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)
    captured = {}

    class UserRepository:
        def __init__(self, _conn):
            pass
        def lock_target(self, _username):
            return SimpleNamespace(
                user_id=42, username="alice", owner_id=7, owner_username="operator"
            )
        def change_group(self, target, **kwargs):
            captured["change"] = kwargs
            return "oldgroup"

    class Groups:
        def __init__(self, _conn):
            pass
        def get_by_name_for_share(self, name):
            assert name == "newgroup"
            return SimpleNamespace(id=22, name="newgroup", owner_id=7)

    class Audit:
        def __init__(self, _conn):
            pass
        def append(self, **kwargs):
            captured["audit"] = kwargs

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "UserAttributeMutationRepository", UserRepository)
    monkeypatch.setattr(users_api, "GroupRepository", Groups)
    monkeypatch.setattr(users_api, "OperationalAuditRepository", Audit)

    result = users_api.change_user_group(
        "alice",
        users_api.UserGroupChange(group_name="newgroup"),
        principal({
            "GET USER INFORMATION": "All",
            "CHANGE USER ATTRIBUTES": "All",
        }),
    )

    assert result.group_name == "newgroup"
    assert result.previous_group_name == "oldgroup"
    assert captured["change"] == {
        "admin_id": 7,
        "group_id": 22,
        "group_name": "newgroup",
    }
    assert captured["audit"]["action"] == "user.group.change"
    assert captured["audit"]["details"] == {
        "previous_group": "oldgroup",
        "new_group": "newgroup",
    }
    assert conn.commits == 1


def test_group_change_rejects_group_outside_admin_access(monkeypatch):
    conn = SimpleNamespace(commits=0)
    conn.commit = lambda: setattr(conn, "commits", conn.commits + 1)

    class UserRepository:
        def __init__(self, _conn):
            pass
        def lock_target(self, _username):
            return SimpleNamespace(
                user_id=42, username="alice", owner_id=7, owner_username="operator"
            )

    class Groups:
        def __init__(self, _conn):
            pass
        def get_by_name_for_share(self, _name):
            return SimpleNamespace(id=22, name="private", owner_id=8)

    install_connection(monkeypatch, conn)
    monkeypatch.setattr(users_api, "UserAttributeMutationRepository", UserRepository)
    monkeypatch.setattr(users_api, "GroupRepository", Groups)

    with pytest.raises(HTTPException) as error:
        users_api.change_user_group(
            "alice",
            users_api.UserGroupChange(group_name="private"),
            principal({
                "GET USER INFORMATION": "All",
                "CHANGE USER ATTRIBUTES": "All",
            }),
        )

    assert error.value.status_code == 403
    assert conn.commits == 0
