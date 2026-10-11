from atd_radius.infrastructure.fast_dial_actions import (
    FastDialActionError,
    FastDialActionsRepository,
)


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, slots=None, target=(42, "alice-voip", 7)):
        self.slots = slots
        self.target = target
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM users u JOIN voip_users" in sql:
            return Result(self.target)
        if "SELECT attr_value FROM user_attrs" in sql:
            return Result((self.slots,) if self.slots is not None else None)
        if "INSERT INTO user_attrs" in sql:
            self.slots = params[2]
            return Result()
        return Result()


def test_missing_fast_dial_attribute_has_ten_empty_slots_and_lookup_returns_empty():
    conn = FakeConnection()
    repo = FastDialActionsRepository(conn)
    assert repo.get_destination(42, 3) == ""
    repo.set_destination(42, 3, "123456")
    assert conn.slots == ",,,123456,,,,,,"
    assert repo.get_destination(42, 3) == "123456"


def test_set_destination_updates_only_requested_slot():
    conn = FakeConnection(slots="0,1,2,3,4,5,6,7,8,9")
    repo = FastDialActionsRepository(conn)
    repo.set_destination(42, 4, "9988")
    assert conn.slots == "0,1,2,3,9988,5,6,7,8,9"


def test_actions_manager_rejects_non_digit_destination_and_indexes_outside_zero_to_nine():
    repo = FastDialActionsRepository(FakeConnection(slots=",".join(str(i) for i in range(10))))
    for index, destination in ((2, "12x"), (-1, "123"), (10, "123")):
        try:
            repo.set_destination(42, index, destination)
        except FastDialActionError:
            pass
        else:
            raise AssertionError("invalid action-manager input should fail")


def test_native_lookup_returns_empty_for_out_of_range_and_negative_indexes():
    repo = FastDialActionsRepository(FakeConnection(slots=",".join(str(i) for i in range(10))))
    assert repo.get_destination(42, 10) == ""
    assert repo.get_destination(42, -1) == ""


def test_target_lookup_uses_voip_username_and_write_path_locks_user_row():
    conn = FakeConnection()
    repo = FastDialActionsRepository(conn)
    target = repo.get_target("alice-voip")
    assert target is not None
    assert (target.user_id, target.voip_username, target.owner_id) == (42, "alice-voip", 7)
    repo.lock_target("alice-voip")
    assert any("FOR UPDATE OF u" in sql for sql, _ in conn.calls)
