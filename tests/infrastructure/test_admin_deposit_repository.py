from decimal import Decimal

from atd_radius.infrastructure.admin_deposit_repository import AdminDepositRepository


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.calls = []
        self.deposit = Decimal("20.00")

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM admins" in sql and "FOR UPDATE" in sql:
            return Result((8, "target-admin", self.deposit))
        if "nextval('admin_deposit_change_id')" in sql:
            return Result((31,))
        if "nextval('ias_event_event_id')" in sql:
            return Result((41,))
        if "UPDATE admins SET deposit = deposit +" in sql:
            self.deposit += params[0]
        return Result(None)


def test_admin_deposit_change_writes_native_log_and_ias_event():
    conn = Connection()
    repo = AdminDepositRepository(conn)
    target = repo.lock_target("target-admin")
    assert target is not None

    result = repo.change(
        target,
        actor_admin_id=7,
        actor_username="operator",
        delta=Decimal("-5.50"),
        remote_addr="192.0.2.20",
        comment="deposit correction",
    )

    assert result == Decimal("14.50")
    assert conn.deposit == Decimal("14.50")
    log = next(params for sql, params in conn.calls if "INSERT INTO admin_deposit_change" in sql)
    assert log == (31, 7, 8, Decimal("-5.50"), "192.0.2.20", "deposit correction")
    ias = next(params for sql, params in conn.calls if "INSERT INTO ias_event" in sql)
    assert ias == (41, "operator", Decimal("-5.50"), "target-admin", "")
