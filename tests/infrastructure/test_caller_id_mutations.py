from atd_radius.infrastructure.caller_id_mutations import expand_caller_ids


def test_caller_id_expansion_matches_a124_multistr_range_padding():
    assert expand_caller_ids("555{1-3},x{n1-3},ab{l04-05}") == [
        "5551", "5552", "5553", "x1", "x2", "x3", "ab04", "ab05"
    ]


def test_caller_id_expansion_rejects_empty_and_duplicate_values():
    import pytest
    from atd_radius.infrastructure.user_attribute_mutations import UserAttributeMutationError

    with pytest.raises(UserAttributeMutationError):
        expand_caller_ids("")
    with pytest.raises(UserAttributeMutationError):
        expand_caller_ids("101,,102")
    with pytest.raises(UserAttributeMutationError):
        expand_caller_ids("101,101")


def test_caller_id_expansion_rejects_invalid_ranges():
    import pytest
    from atd_radius.infrastructure.user_attribute_mutations import UserAttributeMutationError

    with pytest.raises(UserAttributeMutationError):
        expand_caller_ids("555{3-3}")



class FakeCursor:
    def __init__(self, rows=(), one=None):
        self.rows = list(rows)
        self.one = one

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one


class FakeConnection:
    def __init__(self, *, current=(), existing=()):
        self.current = list(current)
        self.existing = list(existing)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT caller_id FROM caller_id_users WHERE user_id" in sql:
            return FakeCursor(rows=[(item,) for item in self.current])
        if "SELECT caller_id FROM caller_id_users WHERE caller_id = ANY" in sql:
            return FakeCursor(rows=[(item,) for item in self.existing])
        if "SELECT value FROM defs WHERE name" in sql:
            return FakeCursor(one=("I1.",))
        return FakeCursor()


def test_caller_id_change_uses_native_table_global_uniqueness_and_audit():
    from atd_radius.infrastructure.caller_id_mutations import CallerIDMutationRepository
    from atd_radius.infrastructure.user_attribute_mutations import UserAttributeTarget

    conn = FakeConnection(current=("1001",))
    target = UserAttributeTarget(42, "alice", 7, "operator")
    result = CallerIDMutationRepository(conn).change(
        target, admin_id=7, expression="100{2-3}"
    )

    assert result == ["1002", "1003"]
    statements = [sql for sql, _ in conn.calls]
    assert "LOCK TABLE caller_id_users IN SHARE ROW EXCLUSIVE MODE" in statements
    assert any("DELETE FROM caller_id_users WHERE user_id" in sql for sql in statements)
    assert sum("INSERT INTO caller_id_users" in sql for sql in statements) == 2
    assert any("insert_user_audit_log" in sql for sql in statements)
    assert all("user_attrs" not in sql for sql in statements)


def test_caller_id_change_rejects_ids_assigned_to_another_user_before_delete():
    import pytest
    from atd_radius.infrastructure.caller_id_mutations import CallerIDMutationRepository
    from atd_radius.infrastructure.user_attribute_mutations import UserAttributeMutationError, UserAttributeTarget

    conn = FakeConnection(current=("1001",), existing=("2002",))
    target = UserAttributeTarget(42, "alice", 7, "operator")
    with pytest.raises(UserAttributeMutationError, match="already assigned"):
        CallerIDMutationRepository(conn).change(
            target, admin_id=7, expression="2002"
        )
    assert not any("DELETE FROM caller_id_users" in sql for sql, _ in conn.calls)
