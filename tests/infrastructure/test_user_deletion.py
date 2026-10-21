from decimal import Decimal

import pytest

from atd_radius.infrastructure.user_deletion import (
    UserDeletionOnlineError,
    UserDeletionRepository,
)


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, *, online_rows=()):
        self.online_rows = list(online_rows)
        self.statements = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.statements.append((normalized, params))
        if "FROM users u" in normalized and "LEFT JOIN normal_users" in normalized:
            return Result([
                (1, 8, Decimal("4.25"), "alice", True),
                (2, 8, Decimal("-3.00"), None, False),
            ])
        if "SELECT DISTINCT user_id FROM atd_radius_live_sessions" in normalized:
            return Result(self.online_rows)
        if "SELECT deposit::numeric FROM admins" in normalized:
            return Result([(Decimal("10.00"),)])
        if "nextval('credit_change_id')" in normalized:
            return Result([(41,)])
        if "SELECT value FROM defs" in normalized:
            return Result([("I1\n.",)])
        if "nextval('ias_event_event_id')" in normalized:
            return Result([(52,)])
        return Result()


def test_user_deletion_refunds_only_nonnegative_credit_and_preserves_history_by_default():
    conn = Connection()
    result = UserDeletionRepository(conn).delete(
        [2, 1],
        admin_id=8,
        admin_username="admin",
        remote_addr="192.0.2.10",
        comment="cleanup",
        delete_connection_logs=False,
        delete_audit_logs=False,
    )

    assert [target.user_id for target in result.targets] == [1, 2]
    assert result.refunded_credit == Decimal("4.25")
    credit = next((sql, params) for sql, params in conn.statements if "INSERT INTO credit_change" in sql)
    assert credit[1] == (41, 8, Decimal("-4.25"), "192.0.2.10", "cleanup")
    ias = next((sql, params) for sql, params in conn.statements if "INSERT INTO ias_event" in sql)
    assert ias[1] == (52, "admin", "1,2")
    assert not any("DELETE FROM connection_log " in sql for sql, _ in conn.statements)
    assert not any("DELETE FROM user_audit_log" in sql for sql, _ in conn.statements)
    assert conn.statements[-1][0] == "DELETE FROM users WHERE user_id = ANY(%s)"


def test_user_deletion_refuses_online_users_before_deleting_rows():
    conn = Connection(online_rows=[(1,)])
    with pytest.raises(UserDeletionOnlineError):
        UserDeletionRepository(conn).delete(
            [1],
            admin_id=8,
            admin_username="admin",
            remote_addr="192.0.2.10",
            comment="cleanup",
            delete_connection_logs=True,
            delete_audit_logs=True,
        )

    assert not any(sql.startswith("DELETE FROM") for sql, _ in conn.statements)
