from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from atd_radius.api import users as users_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.infrastructure.user_deletion import DeletionTarget, UserDeletionResult


class ConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *_args):
        return False


def _principal():
    return AdminPrincipal(8, "admin", "192.0.2.10", Mock())


def test_delete_users_api_checks_permission_audits_and_reports_mailbox_cleanup(monkeypatch):
    conn = Mock()
    target = DeletionTarget(7, 8, Decimal("4.25"), "alice", True)
    repository = Mock()
    repository.lock_targets.return_value = [target]
    repository.delete.return_value = UserDeletionResult((target,), Decimal("4.25"))
    audit = Mock()

    monkeypatch.setattr(users_api, "connection", lambda: ConnectionContext(conn))
    monkeypatch.setattr(users_api, "UserDeletionRepository", lambda _conn: repository)
    monkeypatch.setattr(users_api, "OperationalAuditRepository", lambda _conn: audit)
    monkeypatch.setattr(users_api, "can_delete_user", lambda _admin, owner_id: owner_id == 8)

    result = users_api.delete_users(
        users_api.UserDeletePayload(user_ids=[7], comment="retired account"),
        _principal(),
    )

    assert result.deleted_user_ids == [7]
    assert result.deleted_count == 1
    assert result.refunded_credit == "4.25"
    assert result.mailbox_cleanup_pending == ["alice"]
    repository.delete.assert_called_once()
    audit.append.assert_called_once()
    assert audit.append.call_args.kwargs["action"] == "user.delete"
    conn.commit.assert_called_once()


def test_delete_users_api_rejects_targets_outside_admin_scope(monkeypatch):
    conn = Mock()
    repository = Mock()
    repository.lock_targets.return_value = [DeletionTarget(7, 99, Decimal("1"), "alice", False)]
    monkeypatch.setattr(users_api, "connection", lambda: ConnectionContext(conn))
    monkeypatch.setattr(users_api, "UserDeletionRepository", lambda _conn: repository)
    monkeypatch.setattr(users_api, "can_delete_user", lambda _admin, _owner_id: False)

    with pytest.raises(HTTPException) as exc:
        users_api.delete_users(
            users_api.UserDeletePayload(user_ids=[7], comment="retired account"),
            _principal(),
        )

    assert exc.value.status_code == 403
    repository.delete.assert_not_called()
    conn.commit.assert_not_called()
