from atd_radius.infrastructure.admin_credentials import AdminCredentialRepository


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return Result(self.row)


def test_password_update_changes_only_native_password_and_returns_target():
    conn = Connection((7, "operator"))
    target = AdminCredentialRepository(conn).update_password("operator", "$1$salt$hash")
    assert target is not None
    assert (target.admin_id, target.username) == (7, "operator")
    sql, params = conn.calls[0]
    assert "UPDATE admins" in sql
    assert "SET password = %s" in sql
    assert "RETURNING admin_id, username" in sql
    assert params == ("$1$salt$hash", "operator")


def test_password_update_missing_target_is_not_synthesized():
    assert AdminCredentialRepository(Connection(None)).update_password("missing", "hash") is None
