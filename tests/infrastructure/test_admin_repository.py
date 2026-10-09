from atd_radius.infrastructure.admin_repository import AdminRepository


class Cursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self.results.pop(0)


def test_native_admin_identity_permissions_and_locks_are_loaded_separately():
    conn = FakeConnection([
        Cursor(row=(5, "operator", "Operator", None)),
        Cursor(rows=[("KILL USER", "alice"), ("SEE ONLINE USERS", "")]),
        Cursor(rows=[(9, 2, "incident review")]),
    ])
    repo = AdminRepository(conn)

    admin = repo.get_by_username("operator")
    permissions = repo.permissions(5)
    locks = repo.locks(5)

    assert admin.admin_id == 5
    assert admin.username == "operator"
    assert permissions.has_perm("KILL USER")
    assert permissions.values["KILL USER"] == "alice"
    assert locks[0].lock_id == 9
    assert locks[0].locker_admin_id == 2
    assert "FROM admins" in conn.calls[0][0]
    assert "FROM admin_perms" in conn.calls[1][0]
    assert "FROM admin_locks" in conn.calls[2][0]


def test_missing_admin_is_not_synthesized():
    repo = AdminRepository(FakeConnection([Cursor(row=None)]))
    assert repo.get_by_id(404) is None
