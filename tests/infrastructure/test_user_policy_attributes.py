from atd_radius.infrastructure import UserRepository


class Result:
    def __init__(self, one=None, many=()):
        self.one = one
        self.many = list(many)

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Conn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if sql.startswith("SELECT group_id FROM users"):
            return Result((42,))
        if "FROM group_attrs" in sql:
            return Result(many=(("multi_login", "3"), ("session_timeout", "120")))
        if "FROM user_attrs" in sql:
            return Result(many=(("multi_login", "1"), ("idle_timeout", "30")))
        raise AssertionError(sql)


def test_policy_attributes_merge_group_defaults_with_user_overrides():
    repo = UserRepository(Conn())
    assert repo.policy_attributes(7) == [
        ("multi_login", "1"),
        ("session_timeout", "120"),
        ("idle_timeout", "30"),
    ]


class NativeUserComponentsConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM normal_users" in sql:
            return Result(("alice", "secret"))
        if "FROM voip_users" in sql:
            return Result(("1001", "voip-secret"))
        if "FROM caller_id_users" in sql:
            return Result(many=(("0912",), ("0935",)))
        if "FROM persistent_lan_users" in sql:
            return Result(many=(("00:11:22:33:44:55", "10.0.0.2/32", 7),))
        raise AssertionError(sql)


def test_native_user_components_follow_a124_tables():
    repo = UserRepository(NativeUserComponentsConn())
    assert repo.normal_credentials(7) == ("alice", "secret")
    assert repo.voip_credentials(7) == ("1001", "voip-secret")
    assert repo.caller_ids(7) == ["0912", "0935"]
    assert repo.persistent_lan(7) == [("00:11:22:33:44:55", "10.0.0.2/32", 7)]


def test_is_normal_user_checks_native_normal_users_membership_without_loading_credentials():
    class NormalMembershipConn:
        def __init__(self, exists):
            self.exists = exists
            self.calls = []

        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            assert "SELECT EXISTS (SELECT 1 FROM normal_users WHERE user_id=%s)" in sql
            return Result((self.exists,))

    for expected in (True, False):
        conn = NormalMembershipConn(expected)
        assert UserRepository(conn).is_normal_user(7) is expected
        assert conn.calls == [
            ("SELECT EXISTS (SELECT 1 FROM normal_users WHERE user_id=%s)", (7,))
        ]
