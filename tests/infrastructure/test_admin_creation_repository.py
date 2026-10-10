from atd_radius.infrastructure.admin_creation import AdminCreationRepository


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "nextval('admins_id_seq')" in sql:
            return Result((18,))
        if "INSERT INTO admins" in sql:
            return Result((18, params[1]))
        raise AssertionError(sql)


def test_admin_creation_uses_native_sequence_fields_and_creator():
    conn = Connection()
    created = AdminCreationRepository(conn).create(
        username="new_admin",
        password_hash="$1$12345678$hash",
        name=" New Admin ",
        comment=" note ",
        creator_id=7,
    )
    assert (created.admin_id, created.username) == (18, "new_admin")
    assert conn.calls[0] == ("SELECT nextval('admins_id_seq')", ())
    sql, params = conn.calls[1]
    assert "INSERT INTO admins" in sql
    assert "(admin_id, username, password, name, comment, creator_id, deposit, due)" in sql
    assert params == (18, "new_admin", "$1$12345678$hash", "New Admin", "note", 7)
