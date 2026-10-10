from decimal import Decimal

import pytest

from atd_radius.infrastructure.admin_deletion import (
    AdminDeletionError,
    AdminDeletionRepository,
)


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, *, target=("8", "target", "12.50"), ias_enabled="I1\n."):
        self.target = target
        self.ias_enabled = ias_enabled
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT admin_id, username, deposit::numeric" in sql:
            return Result(self.target if params == ("target",) else None)
        if "SELECT value FROM defs WHERE name = %s" in sql:
            return Result((self.ias_enabled,))
        if "nextval('ias_event_event_id')" in sql:
            return Result((901,))
        return Result()


def test_admin_delete_reproduces_native_side_effects_and_ias_event():
    conn = Connection()
    result = AdminDeletionRepository(conn).delete("target", deleter_username="operator")
    assert (result.admin_id, result.username, result.deposit) == (8, "target", Decimal("12.50"))
    sql = [statement for statement, _ in conn.calls]
    required = [
        "DELETE FROM admin_locks WHERE admin_id = %s",
        "DELETE FROM admin_deposit_change WHERE to_admin_id = %s",
        "DELETE FROM admin_perms WHERE admin_id = %s",
        "DELETE FROM add_user_save_details",
        "DELETE FROM add_user_saves WHERE admin_id = %s",
        "UPDATE users SET owner_id = 0 WHERE owner_id = %s",
        "UPDATE groups SET owner_id = 0 WHERE owner_id = %s",
        "UPDATE admin_locks SET locker_admin_id = 0 WHERE locker_admin_id = %s",
        "UPDATE credit_change SET admin_id = 0 WHERE admin_id = %s",
        "UPDATE admin_deposit_change SET admin_id = 0 WHERE admin_id = %s",
        "UPDATE user_audit_log SET admin_id = 0 WHERE admin_id = %s",
        "DELETE FROM admins WHERE admin_id = %s",
        "UPDATE admins SET creator_id = 0 WHERE creator_id = %s",
        "INSERT INTO ias_event",
    ]
    positions = [next(i for i, statement in enumerate(sql) if required_item in statement) for required_item in required]
    assert positions == sorted(positions)
    event = next(params for statement, params in conn.calls if "INSERT INTO ias_event" in statement)
    assert event == (901, "operator", Decimal("12.50"), "target", "")


def test_admin_delete_skips_ias_event_when_native_flag_is_disabled():
    conn = Connection(ias_enabled="I0\n.")
    AdminDeletionRepository(conn).delete("target", deleter_username="operator")
    assert not any("nextval('ias_event_event_id')" in sql for sql, _ in conn.calls)
    assert not any("INSERT INTO ias_event" in sql for sql, _ in conn.calls)


def test_admin_delete_protects_native_system_account():
    conn = Connection(target=(0, "system", "0"))
    with pytest.raises(AdminDeletionError) as error:
        AdminDeletionRepository(conn).delete("system", deleter_username="operator")
    assert error.value.code == "system_admin_protected"
    assert len(conn.calls) == 1


def test_admin_delete_requires_existing_admin():
    conn = Connection(target=None)
    with pytest.raises(AdminDeletionError) as error:
        AdminDeletionRepository(conn).delete("missing", deleter_username="operator")
    assert error.value.code == "admin_not_found"
    assert len(conn.calls) == 1
