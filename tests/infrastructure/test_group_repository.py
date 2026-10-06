from __future__ import annotations

from atd_radius.infrastructure.group import GroupRepository


def test_group_name_validation_matches_a124_name_charset() -> None:
    GroupRepository._validate_name("group_01-test")
    for value in ("", "group name", "گروه"):
        try:
            GroupRepository._validate_name(value)
        except ValueError:
            continue
        raise AssertionError(value)


def test_group_record_mapping() -> None:
    record = GroupRepository._record((7, "test_group", 2, "comment"))
    assert record.id == 7
    assert record.name == "test_group"
    assert record.owner_id == 2
    assert record.comment == "comment"


def test_group_update_uses_native_set_columns_then_group_id():
    class Result:
        def fetchone(self):
            return (7, "old", 2, "old comment")

        def fetchall(self):
            return []

    class Conn:
        def __init__(self):
            self.calls = []

        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            if sql.startswith("SELECT group_id, group_name") and "WHERE group_id=%s" in sql:
                return Result()
            if sql.startswith("SELECT group_id, group_name") and "WHERE group_name=%s" in sql:
                class Empty:
                    def fetchone(self):
                        return None
                return Empty()
            return Result()

    conn = Conn()
    repo = GroupRepository(conn)
    repo.update(7, "new", "new comment", 3)
    sql, params = conn.calls[-1]
    assert sql == "UPDATE groups SET group_name=%s, owner_id=%s, comment=%s WHERE group_id=%s"
    assert params == ("new", 3, "new comment", 7)
