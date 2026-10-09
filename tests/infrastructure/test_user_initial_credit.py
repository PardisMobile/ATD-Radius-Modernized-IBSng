from decimal import Decimal

from atd_radius.infrastructure import UserRepository


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "nextval('users_user_id_seq')" in sql:
            return Result((42,))
        return Result(None)


def test_user_repository_persists_initial_credit_in_native_users_row():
    conn = Connection()
    record = UserRepository(conn).create(
        "alice",
        owner_id=7,
        group_id=2,
        initial_credit=Decimal("12.50"),
    )

    assert record.id == 42
    assert (
        "INSERT INTO users (user_id, credit, owner_id, group_id) VALUES (%s, %s, %s, %s)",
        (42, Decimal("12.50"), 7, 2),
    ) in conn.calls
