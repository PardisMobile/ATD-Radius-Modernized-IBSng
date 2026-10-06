from decimal import Decimal

from atd_radius.infrastructure.credit_repository import UserCreditRepository


class Result:
    def __init__(self, row):
        self.row = row
    def fetchone(self):
        return self.row


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
