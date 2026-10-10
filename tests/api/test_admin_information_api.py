from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.admins as admins_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet


def principal(perms=None):
    return AdminPrincipal(7, "operator", "192.0.2.20", AdminPermissionSet(perms or {}))


def install_repository(monkeypatch, repo):
    @contextmanager
    def fake_connection():
        yield object()

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminInformationRepository", lambda _conn: repo)


def test_admin_username_list_is_self_only_without_see_permission(monkeypatch):
    class Repo:
        def list_usernames(self):
            raise AssertionError("restricted listing must not query all administrators")

    install_repository(monkeypatch, Repo())
    assert admins_api.list_admin_usernames(principal({})) == ["operator"]


def test_admin_username_list_is_sorted_repository_result_with_permission(monkeypatch):
    class Repo:
        def list_usernames(self):
            return ["alpha", "operator", "zeta"]

    install_repository(monkeypatch, Repo())
    assert admins_api.list_admin_usernames(principal({"SEE ADMIN INFO": ""})) == ["alpha", "operator", "zeta"]


def test_admin_detail_allows_self_but_denies_other_admin_without_permission(monkeypatch):
    class Repo:
        def get_by_username(self, username):
            return SimpleNamespace(
                admin_id=7,
                username=username,
                name="Operator",
                comment=None,
                deposit=Decimal("10.00"),
                creator_id=None,
                creator=None,
                locks=(),
            )

    install_repository(monkeypatch, Repo())
    self_view = admins_api.get_admin_information("operator", principal({}))
    assert self_view.deposit == "10.00"

    with pytest.raises(HTTPException) as denied:
        admins_api.get_admin_information("another", principal({}))
    assert denied.value.status_code == 403



def test_admin_info_update_requires_source_permission_chain(monkeypatch):
    from atd_radius.api.admin_dependencies import require_admin_permission

    dependency = require_admin_permission("CHANGE ADMIN INFO")
    with pytest.raises(HTTPException) as denied:
        dependency(principal({"CHANGE ADMIN INFO": ""}))
    assert denied.value.status_code == 403

    allowed = dependency(principal({"SEE ADMIN INFO": "", "CHANGE ADMIN INFO": ""}))
    assert allowed.admin_id == 7


def test_admin_info_update_commits_native_update_and_operational_audit(monkeypatch):
    from datetime import datetime, timezone

    class Conn:
        def __init__(self):
            self.commits = 0
            self.calls = []

        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            if "INSERT INTO operational_audit_events" in sql:
                return type("Result", (), {"fetchone": lambda self: (99, datetime(2026, 10, 10, tzinfo=timezone.utc))})()
            return type("Result", (), {"fetchone": lambda self: (7,)})()

        def commit(self):
            self.commits += 1

    conn = Conn()
    updated = SimpleNamespace(
        admin_id=8, username="target", name="Updated", comment="new comment",
        deposit=Decimal("10.00"), creator_id=7, creator="operator", locks=(),
    )
    class Repo:
        def __init__(self, _conn):
            pass
        def update_info(self, username, name, comment):
            assert (username, name, comment) == ("target", "Updated", "new comment")
            return updated

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminInformationRepository", Repo)
    monkeypatch.setattr(admins_api, "OperationalAuditRepository", lambda _conn: type("Audit", (), {"append": lambda self, **kwargs: None})())

    result = admins_api.update_admin_information(
        "target",
        admins_api.AdminInformationUpdate(name="Updated", comment="new comment"),
        principal({"SEE ADMIN INFO": "", "CHANGE ADMIN INFO": ""}),
    )
    assert result.name == "Updated"
    assert conn.commits == 1



def test_admin_lock_and_unlock_require_change_admin_info_dependencies():
    from atd_radius.api.admin_dependencies import require_admin_permission

    dependency = require_admin_permission("CHANGE ADMIN INFO")
    with pytest.raises(HTTPException) as denied:
        dependency(principal({"CHANGE ADMIN INFO": ""}))
    assert denied.value.status_code == 403
    assert dependency(principal({"SEE ADMIN INFO": "", "CHANGE ADMIN INFO": ""})).admin_id == 7


def test_lock_admin_commits_native_lock_and_operational_audit(monkeypatch):
    conn = type("Conn", (), {"commits": 0, "commit": lambda self: setattr(self, "commits", self.commits + 1)})()
    updated = SimpleNamespace(
        admin_id=8, username="target", name="Target", comment="", deposit=Decimal("0"),
        creator_id=7, creator="operator",
        locks=(SimpleNamespace(lock_id=91, locker_admin="operator", reason="security review"),),
    )
    class Repo:
        def __init__(self, _conn): pass
        def lock_admin(self, username, *, reason, locker_admin_id):
            assert (username, reason, locker_admin_id) == ("target", "security review", 7)
            return updated
    class Audit:
        def __init__(self, _conn): pass
        def append(self, **kwargs):
            assert kwargs["action"] == "admin.lock"
            assert kwargs["target_id"] == "8"
    @contextmanager
    def fake_connection():
        yield conn
    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminInformationRepository", Repo)
    monkeypatch.setattr(admins_api, "OperationalAuditRepository", Audit)
    result = admins_api.lock_admin(
        "target", admins_api.AdminLockCreate(reason="security review"),
        principal({"SEE ADMIN INFO": "", "CHANGE ADMIN INFO": ""}),
    )
    assert [lock.lock_id for lock in result.locks] == [91]
    assert conn.commits == 1


def test_unlock_admin_returns_404_for_missing_target_lock(monkeypatch):
    @contextmanager
    def fake_connection():
        yield object()
    class Repo:
        def __init__(self, _conn): pass
        def unlock_admin(self, username, lock_id):
            assert (username, lock_id) == ("target", 91)
            return None
    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminInformationRepository", Repo)
    with pytest.raises(HTTPException) as missing:
        admins_api.unlock_admin(
            "target", 91, principal({"SEE ADMIN INFO": "", "CHANGE ADMIN INFO": ""})
        )
    assert missing.value.status_code == 404



def test_admin_creation_persists_native_fields_and_audits_without_password(monkeypatch):
    from atd_radius.domain.ibsng_password import verify_ibsng_password

    conn = type("Conn", (), {"commits": 0, "commit": lambda self: setattr(self, "commits", self.commits + 1)})()
    captured = {}

    class CreationRepo:
        def __init__(self, _conn):
            pass

        def create(self, **kwargs):
            captured["create"] = kwargs
            return SimpleNamespace(admin_id=18, username=kwargs["username"])

    class InfoRepo:
        def __init__(self, _conn):
            pass

        def get_by_username(self, username):
            return SimpleNamespace(
                admin_id=18, username=username, name="New Admin", comment="hello",
                deposit=Decimal("0"), creator_id=7, creator="operator", locks=(),
            )

    class Audit:
        def __init__(self, _conn):
            pass

        def append(self, **kwargs):
            captured["audit"] = kwargs

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminCreationRepository", CreationRepo)
    monkeypatch.setattr(admins_api, "AdminInformationRepository", InfoRepo)
    monkeypatch.setattr(admins_api, "OperationalAuditRepository", Audit)
    view = admins_api.create_admin(
        admins_api.AdminCreate(
            username="new_admin7", password="Secret_123", name=" New Admin ",
            comment=" hello ",
        ),
        principal({"ADD NEW ADMIN": ""}),
    )
    assert (view.admin_id, view.username, view.creator_id) == (18, "new_admin7", 7)
    assert captured["create"]["creator_id"] == 7
    assert captured["create"]["name"] == " New Admin "
    assert verify_ibsng_password("Secret_123", captured["create"]["password_hash"])
    assert captured["audit"]["action"] == "admin.create"
    assert "password_hash" not in str(captured["audit"])
    assert conn.commits == 1


def test_admin_creation_rejects_invalid_username_and_password_before_database(monkeypatch):
    @contextmanager
    def no_connection():
        raise AssertionError("invalid input must be rejected before database access")
        yield

    monkeypatch.setattr(admins_api, "connection", no_connection)
    with pytest.raises(HTTPException) as bad_username:
        admins_api.create_admin(
            admins_api.AdminCreate(username="7bad", password="Secret_123", name="A", comment=""),
            principal({"ADD NEW ADMIN": ""}),
        )
    assert bad_username.value.status_code == 422

    with pytest.raises(HTTPException) as bad_password:
        admins_api.create_admin(
            admins_api.AdminCreate(username="valid", password="has space", name="A", comment=""),
            principal({"ADD NEW ADMIN": ""}),
        )
    assert bad_password.value.status_code == 422
