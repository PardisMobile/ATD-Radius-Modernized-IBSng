from __future__ import annotations

from atd_radius.infrastructure.ras import RASRepository


def test_ras_record_mapping_preserves_native_columns() -> None:
    record = RASRepository._ras((3, "router", "192.0.2.10", "Mikrotik", "secret", True, "test"))
    assert record.ras_id == 3
    assert record.description == "router"
    assert record.ip == "192.0.2.10"
    assert record.ras_type == "Mikrotik"
    assert record.radius_secret == "secret"
    assert record.active is True
    assert record.comment == "test"


def test_ras_repository_change_hook_is_called_for_mutations() -> None:
    class FakeResult:
        def __init__(self, row=None):
            self.row = row
        def fetchone(self):
            return self.row
        def fetchall(self):
            return []

    class FakeConnection:
        def __init__(self):
            self.calls = []
        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            if "nextval" in sql:
                return FakeResult((9,))
            if "SELECT ras_id FROM ras_ippools" in sql:
                return FakeResult((4,))
            if "INSERT INTO ras_ippools" in sql:
                return FakeResult((12,))
            return FakeResult()

    changed = []
    conn = FakeConnection()
    repo = RASRepository(conn, on_change=changed.append)
    repo.create("r", "192.0.2.9", "Mikrotik", "s")
    repo.upsert_port(9, "p1", None, None, None)
    repo.delete_port(9, "p1")
    repo.set_attribute(9, "x", "1")
    repo.delete_attribute(9, "x")
    repo.add_ippool(9, 2)
    repo.delete_ippool(4)
    assert changed == [9, 9, 9, 9, 9, 9, 4]
