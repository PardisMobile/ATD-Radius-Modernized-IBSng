from atd_radius.infrastructure.user_charge_assignments import (
    UserChargeAssignmentRepository,
    UserChargeNotFound,
    UserChargeTypeError,
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
    def __init__(self, *, charge=(11, "InternetPlan", "Internet"), current=None, audit_flag="I1\n."):
        self.charge = charge
        self.current = current
        self.audit_flag = audit_flag
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM users u" in sql and "FOR UPDATE OF u" in sql:
            return Result((42, 7, "alice"))
        if "SELECT charge_id, name, charge_type" in sql and "WHERE name=%s" in sql:
            return Result(self.charge)
        if "SELECT attr_value FROM user_attrs" in sql:
            return Result((self.current,) if self.current is not None else None)
        if "INSERT INTO user_attrs" in sql and "ON CONFLICT" in sql:
            self.current = params[2]
            return Result()
        if "DELETE FROM user_attrs" in sql:
            self.current = None
            return Result()
        if "SELECT value FROM defs" in sql:
            return Result((self.audit_flag,) if self.audit_flag is not None else None)
        if "SELECT name FROM charges WHERE charge_id" in sql:
            return Result(("InternetPlan",))
        if "SELECT insert_user_audit_log" in sql:
            return Result((1,))
        return Result()


def test_normal_charge_assignment_persists_native_id_and_audits_names():
    conn = FakeConnection()
    repo = UserChargeAssignmentRepository(conn)
    target = repo.lock_target("alice", "normal_charge")
    assert target is not None
    assigned = repo.assign(target, admin_id=7, charge_name="InternetPlan")
    assert assigned.charge_id == 11
    assert assigned.charge_name == "InternetPlan"
    assert conn.current == "11"
    audit = [params for sql, params in conn.calls if "SELECT insert_user_audit_log" in sql]
    assert audit == [(7, 42, "normal_charge", "_NOVALUE_", "InternetPlan")]


def test_reassigning_same_charge_does_not_duplicate_native_audit():
    conn = FakeConnection(current="11")
    repo = UserChargeAssignmentRepository(conn)
    target = repo.lock_target("alice", "normal_charge")
    assert target is not None
    repo.assign(target, admin_id=7, charge_name="InternetPlan")
    assert not any("INSERT INTO user_attrs" in sql for sql, _ in conn.calls)
    assert not any("SELECT insert_user_audit_log" in sql for sql, _ in conn.calls)


def test_voip_charge_assignment_rejects_internet_charge():
    conn = FakeConnection(charge=(11, "InternetPlan", "Internet"))
    repo = UserChargeAssignmentRepository(conn)
    target = repo.lock_target("alice", "voip_charge")
    assert target is not None
    import pytest
    with pytest.raises(UserChargeTypeError):
        repo.assign(target, admin_id=7, charge_name="InternetPlan")


def test_delete_charge_assignment_audits_previous_charge_name():
    conn = FakeConnection(current="11")
    repo = UserChargeAssignmentRepository(conn)
    target = repo.lock_target("alice", "normal_charge")
    assert target is not None
    deleted = repo.delete(target, admin_id=7)
    assert deleted.charge_id is None
    assert conn.current is None
    audit = [params for sql, params in conn.calls if "SELECT insert_user_audit_log" in sql]
    assert audit == [(7, 42, "normal_charge", "InternetPlan", "_NOVALUE_")]


def test_missing_charge_is_rejected_before_attribute_write():
    conn = FakeConnection(charge=None)
    repo = UserChargeAssignmentRepository(conn)
    target = repo.lock_target("alice", "normal_charge")
    assert target is not None
    import pytest
    with pytest.raises(UserChargeNotFound):
        repo.assign(target, admin_id=7, charge_name="missing")
    assert not any("INSERT INTO user_attrs" in sql for sql, _ in conn.calls)
