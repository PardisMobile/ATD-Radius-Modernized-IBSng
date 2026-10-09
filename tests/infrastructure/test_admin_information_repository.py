from decimal import Decimal

from atd_radius.infrastructure.admin_information import AdminInformationRepository


class Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = list(rows or [])

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT admin_id FROM admins WHERE username" in sql:
            return Result((8,))
        if "FROM admins a" in sql:
            return Result((8, "target", "Target Admin", "comment", Decimal("15.50"), 7, "operator"))
        if "FROM admin_locks l" in sql:
            return Result(rows=[(3, "operator", "review"), (4, "root", "manual")])
        if sql.startswith("SELECT username FROM admins"):
            return Result(rows=[("alpha",), ("operator",), ("target",)])
        raise AssertionError(sql)


def test_admin_information_reads_native_identity_creator_deposit_and_locks():
    conn = Connection()
    repo = AdminInformationRepository(conn)
    record = repo.get_by_username("target")

    assert record is not None
    assert (record.admin_id, record.username, record.deposit) == (8, "target", Decimal("15.50"))
    assert (record.creator_id, record.creator) == (7, "operator")
    assert [(lock.lock_id, lock.locker_admin) for lock in record.locks] == [(3, "operator"), (4, "root")]


def test_admin_information_username_list_is_sorted_by_database_contract():
    conn = Connection()
    assert AdminInformationRepository(conn).list_usernames() == ["alpha", "operator", "target"]
    assert "ORDER BY username" in conn.calls[0][0]



def test_admin_information_update_locks_target_and_changes_only_name_comment():
    conn = Connection()
    repo = AdminInformationRepository(conn)
    record = repo.update_info("target", "Updated", "new comment")

    assert record is not None
    assert any("FOR UPDATE" in sql for sql, _ in conn.calls)
    assert (
        "UPDATE admins SET name = %s, comment = %s WHERE admin_id = %s",
        ("Updated", "new comment", 8),
    ) in conn.calls
