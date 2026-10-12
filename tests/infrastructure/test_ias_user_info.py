from decimal import Decimal

import pytest

from atd_radius.infrastructure.ias_user_info import PostgresIASUserInfoRepository


class Result:
    def __init__(self, rows):
        self.rows = rows
    def fetchall(self):
        return self.rows


class Conn:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return Result(self.rows)


def test_ias_user_info_maps_native_owner_credit_and_usernames_in_requested_order():
    conn = Conn([
        (2, "root", Decimal("10.00"), "alice", None),
        (1, "admin", Decimal("5.00"), None, "voip-alice"),
    ])
    users = PostgresIASUserInfoRepository(conn).get_many([2, 1])
    assert [user.user_id for user in users] == [2, 1]
    assert users[0].owner == "root"
    assert users[0].credit == Decimal("10.00")
    assert users[0].normal_username == "alice"
    assert users[1].voip_username == "voip-alice"
    assert "array_position" in conn.calls[0][0]
    assert conn.calls[0][1] == ([2, 1], [2, 1])


def test_ias_user_info_rejects_missing_duplicate_and_unbounded_ids():
    repo = PostgresIASUserInfoRepository(Conn([]))
    with pytest.raises(ValueError):
        repo.get_many([0])
    with pytest.raises(ValueError):
        repo.get_many([1, 1])
    with pytest.raises(ValueError):
        repo.get_many(list(range(1, 1002)))
    with pytest.raises(LookupError):
        repo.get_many([1])
