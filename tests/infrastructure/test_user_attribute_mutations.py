from atd_radius.infrastructure.user_attribute_mutations import (
    AUDIT_LOG_NOVALUE,
    UserAttributeMutationError,
    UserAttributeMutationRepository,
)


class Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = list(rows) if rows is not None else ([row] if row is not None else [])

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, current=None, audit_flag="I1\n."):
        self.current = dict(current or {})
        self.audit_flag = audit_flag
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM users u" in sql and "FOR UPDATE OF u" in sql:
            return Result((42, "alice", 7, "operator"))
        if "SELECT attr_name, attr_value" in sql and "ANY(%s)" in sql:
            return Result(rows=[(name, value) for name, value in self.current.items() if name in params[1]])
        if "SELECT admin_id, username FROM admins" in sql:
            return Result((9, "newowner"))
        if "SELECT value FROM defs" in sql:
            return Result((self.audit_flag,) if self.audit_flag is not None else None)
        if "UPDATE user_attrs SET" in sql:
            value, _user_id, name = params
            self.current[name] = value
            return Result()
        if "INSERT INTO user_attrs" in sql:
            user_id, name, value = params
            self.current[name] = value
            return Result()
        if "DELETE FROM user_attrs" in sql:
            _user_id, name = params
            self.current.pop(name, None)
            return Result()
        if "SELECT insert_user_audit_log" in sql:
            return Result((1,))
        if "SELECT attr_name, attr_value FROM user_attrs WHERE user_id" in sql:
            return Result(rows=sorted(self.current.items()))
        return Result()


def test_generic_comment_plugin_family_changes_and_deletes_with_native_audit():
    conn = FakeConnection(current={"name": "Old", "phone": "123"})
    repo = UserAttributeMutationRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None

    result = repo.apply(
        target,
        admin_id=9,
        attrs={"name": "New", "comment": "VIP"},
        to_delete=["phone"],
    )

    assert result.attributes == [("comment", "VIP"), ("name", "New")]
    audit_calls = [(sql, params) for sql, params in conn.calls if "SELECT insert_user_audit_log" in sql]
    assert [params[2:] for _, params in audit_calls] == [
        ("name", "Old", "New"),
        ("comment", AUDIT_LOG_NOVALUE, "VIP"),
        ("phone", "123", AUDIT_LOG_NOVALUE),
    ]


def test_same_value_is_not_written_to_native_user_audit_log():
    conn = FakeConnection(current={"name": "Alice"})
    repo = UserAttributeMutationRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None

    repo.apply(target, admin_id=9, attrs={"name": "Alice"}, to_delete=[])

    assert not any("SELECT insert_user_audit_log" in sql for sql, _ in conn.calls)


def test_unknown_specialized_attribute_is_rejected_before_attribute_writes():
    conn = FakeConnection()
    repo = UserAttributeMutationRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None

    try:
        repo.apply(target, admin_id=9, attrs={"radius_attrs": "Session-Timeout=\"2\""}, to_delete=[])
    except UserAttributeMutationError as exc:
        assert "specialized A1.24 handler" in str(exc)
    else:
        raise AssertionError("specialized attribute must not use generic persistence")

    assert not any("INSERT INTO user_attrs" in sql or "UPDATE user_attrs" in sql for sql, _ in conn.calls)


def test_multi_login_and_timeout_handlers_apply_source_validation_and_normalization():
    conn = FakeConnection()
    repo = UserAttributeMutationRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None

    result = repo.apply(
        target,
        admin_id=9,
        attrs={"multi_login": "025", "session_timeout": " 60 ", "idle_timeout": "+15", "lock": "abuse"},
        to_delete=[],
    )

    assert result.attributes == [
        ("idle_timeout", "15"),
        ("lock", "abuse"),
        ("multi_login", "25"),
        ("session_timeout", "60"),
    ]
    audit_calls = [params for sql, params in conn.calls if "SELECT insert_user_audit_log" in sql]
    assert [row[2:] for row in audit_calls] == [
        ("multi_login", AUDIT_LOG_NOVALUE, "25"),
        ("session_timeout", AUDIT_LOG_NOVALUE, "60"),
        ("idle_timeout", AUDIT_LOG_NOVALUE, "15"),
        ("lock", AUDIT_LOG_NOVALUE, "abuse"),
    ]


def test_multi_login_rejects_non_integer_and_out_of_range_values_before_writes():
    for invalid in ("not-a-number", "-1", "256"):
        conn = FakeConnection()
        repo = UserAttributeMutationRepository(conn)
        target = repo.lock_target("alice")
        assert target is not None

        try:
            repo.apply(target, admin_id=9, attrs={"multi_login": invalid}, to_delete=[])
        except UserAttributeMutationError:
            pass
        else:
            raise AssertionError(f"multi_login value {invalid!r} should be rejected")

        assert not any("INSERT INTO user_attrs" in sql or "UPDATE user_attrs" in sql for sql, _ in conn.calls)


def test_user_audit_log_flag_off_disables_native_attribute_audit():
    conn = FakeConnection(current={}, audit_flag="I0\n.")
    repo = UserAttributeMutationRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None

    repo.apply(target, admin_id=9, attrs={"comment": "private note"}, to_delete=[])

    assert not any("SELECT insert_user_audit_log" in sql for sql, _ in conn.calls)


def test_owner_transfer_uses_users_owner_id_and_native_owner_audit():
    conn = FakeConnection()
    repo = UserAttributeMutationRepository(conn)
    target = repo.lock_target("alice")
    assert target is not None

    owner = repo.change_owner(target, admin_id=7, owner_username="newowner")

    assert owner == "newowner"
    assert any(
        "UPDATE users SET owner_id" in sql and params == (9, 42)
        for sql, params in conn.calls
    )
    audit_calls = [params for sql, params in conn.calls if "SELECT insert_user_audit_log" in sql]
    assert [row[2:] for row in audit_calls] == [("owner", "operator", "newowner")]
