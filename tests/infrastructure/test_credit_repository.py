from decimal import Decimal

from atd_radius.infrastructure.credit_repository import UserCreditRepository


class Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = list(rows) if rows is not None else ([row] if row is not None else [])

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Conn:
    def __init__(self):
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if sql.startswith("SELECT credit::numeric"):
            return Result((Decimal("25.50"),))
        if sql.startswith("SELECT change_user_credit"):
            return Result((1,))
        raise AssertionError(sql)


def test_credit_repository_uses_native_credit_column_and_function():
    conn = Conn()
    repo = UserCreditRepository(conn)
    assert repo.change(7, Decimal("-2.50")) == Decimal("25.50")
    assert conn.calls[0] == (
        "SELECT change_user_credit(%s, %s::numeric)",
        (7, Decimal("-2.50")),
    )
    assert repo.get(7) == Decimal("25.50")

class AdminCreditConn:
    def __init__(self, *, user_credit="25.00", owner_id=7, deposit="100.00"):
        self.calls = []
        self.user_row = (42, "alice", owner_id, Decimal(user_credit))
        self.deposit = Decimal(deposit)

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FOR UPDATE OF u" in sql:
            return Result(self.user_row)
        if "FROM admins" in sql and "FOR UPDATE" in sql:
            return Result((self.deposit,))
        if "nextval('credit_change_id')" in sql:
            return Result((101,))
        if "nextval('ias_event_event_id')" in sql:
            return Result((501,))
        return Result(None)


def test_admin_credit_change_locks_target_and_writes_native_logs_atomically():
    from atd_radius.infrastructure.credit_repository import UserCreditRepository

    conn = AdminCreditConn(user_credit="25.00", deposit="100.00")
    repo = UserCreditRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None
    assert (target.user_id, target.owner_id, target.credit) == (42, 7, Decimal("25.00"))

    result = repo.apply_admin_change(
        target,
        admin_id=7,
        admin_username="operator",
        delta=Decimal("12.50"),
        remote_addr="192.0.2.20",
        comment="top-up",
        allow_negative_deposit=False,
    )
    assert result == Decimal("37.50")
    assert ("UPDATE users SET credit = %s WHERE user_id = %s", (Decimal("37.50"), 42)) in conn.calls
    assert ("UPDATE admins SET deposit = %s WHERE admin_id = %s", (Decimal("87.50"), 7)) in conn.calls
    credit_log = next(call for call in conn.calls if "INSERT INTO credit_change" in call[0])
    assert credit_log[1] == (101, 7, Decimal("12.50"), Decimal("12.50"), "192.0.2.20", "top-up")
    assert ("INSERT INTO credit_change_userid (credit_change_id, user_id) VALUES (%s, %s)", (101, 42)) in conn.calls
    ias_log = next(call for call in conn.calls if "INSERT INTO ias_event" in call[0])
    assert ias_log[1] == (501, "operator", Decimal("12.50"), "42", "top-up")


def test_admin_credit_change_rejects_negative_user_credit_before_writes():
    import pytest
    from atd_radius.infrastructure.credit_repository import CreditUnderflowError, UserCreditRepository

    conn = AdminCreditConn(user_credit="1.00")
    repo = UserCreditRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None
    with pytest.raises(CreditUnderflowError):
        repo.apply_admin_change(
            target,
            admin_id=7,
            admin_username="operator",
            delta=Decimal("-2.00"),
            remote_addr="192.0.2.20",
            comment="invalid debit",
            allow_negative_deposit=False,
        )
    assert not any(sql.startswith("UPDATE ") or sql.startswith("INSERT ") for sql, _ in conn.calls)


def test_admin_credit_change_respects_deposit_limit_unless_source_permission_allows_it():
    import pytest
    from atd_radius.infrastructure.credit_repository import (
        InsufficientAdminDepositError,
        UserCreditRepository,
    )

    conn = AdminCreditConn(user_credit="1.00", deposit="2.00")
    repo = UserCreditRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None
    with pytest.raises(InsufficientAdminDepositError):
        repo.apply_admin_change(
            target,
            admin_id=7,
            admin_username="operator",
            delta=Decimal("3.00"),
            remote_addr="192.0.2.20",
            comment="too much",
            allow_negative_deposit=False,
        )
    assert not any(sql.startswith("UPDATE ") or sql.startswith("INSERT ") for sql, _ in conn.calls)

    assert repo.apply_admin_change(
        target,
        admin_id=7,
        admin_username="operator",
        delta=Decimal("3.00"),
        remote_addr="192.0.2.20",
        comment="allowed by native permission",
        allow_negative_deposit=True,
    ) == Decimal("4.00")

