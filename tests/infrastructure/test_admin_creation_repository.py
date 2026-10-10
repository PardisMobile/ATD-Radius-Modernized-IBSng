from atd_radius.infrastructure.admin_creation import AdminCreationRepository


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, ias_enabled="I1\\n."):
        self.calls = []
        self.ias_enabled = ias_enabled

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT value FROM defs WHERE name = %s" in sql:
            assert params == ("IAS_ENABLED",)
            return Result((self.ias_enabled,))
        if "nextval('admins_id_seq')" in sql:
            return Result((18,))
        if "INSERT INTO admins" in sql:
            return Result((18, params[1]))
        if "nextval('ias_event_event_id')" in sql:
            return Result((901,))
        if "INSERT INTO ias_event" in sql:
            return Result(None)
        raise AssertionError(sql)


def test_admin_creation_uses_native_sequence_fields_and_creator():
    conn = Connection()
    created = AdminCreationRepository(conn).create(
        username="new_admin",
        password_hash="$1$12345678$hash",
        name=" New Admin ",
        comment=" note ",
        creator_id=7,
        creator_username="operator",
    )
    assert (created.admin_id, created.username) == (18, "new_admin")
    assert conn.calls[0] == ("SELECT nextval('admins_id_seq')", ())
    sql, params = conn.calls[1]
    assert "INSERT INTO admins" in sql
    assert "(admin_id, username, password, name, comment, creator_id, deposit, due)" in sql
    assert params == (18, "new_admin", "$1$12345678$hash", "New Admin", "note", 7)
    assert "SELECT value FROM defs WHERE name = %s" in conn.calls[2][0]
    assert "nextval('ias_event_event_id')" in conn.calls[3][0]
    event_sql, event_params = conn.calls[4]
    assert "INSERT INTO ias_event" in event_sql
    assert event_params == (901, "operator", "new_admin", "")


def test_admin_creation_does_not_emit_ias_event_when_native_flag_is_disabled():
    conn = Connection(ias_enabled="I0\\n.")
    created = AdminCreationRepository(conn).create(
        username="new_admin",
        password_hash="$1$12345678$hash",
        name="New Admin",
        comment="note",
        creator_id=7,
        creator_username="operator",
    )
    assert (created.admin_id, created.username) == (18, "new_admin")
    assert not any("nextval('ias_event_event_id')" in sql for sql, _ in conn.calls)
    assert not any("INSERT INTO ias_event" in sql for sql, _ in conn.calls)
