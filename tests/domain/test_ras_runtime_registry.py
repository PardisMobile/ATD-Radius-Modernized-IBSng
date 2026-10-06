from __future__ import annotations

from atd_radius.domain.ras import RASRuntimeRegistry
from atd_radius.infrastructure.ras import RASIPPoolRecord, RASPortRecord, RASRecord


class FakeRASRepository:
    def __init__(self) -> None:
        self.records = [
            RASRecord(2, "router-2", "192.0.2.2", "Mikrotik", "s2", True, None),
            RASRecord(1, "router-1", "192.0.2.1", "Cisco", "s1", True, None),
        ]
        self._attrs = {
            1: [("online_check", "0"), ("ras_multi_login", "0")],
            2: [("online_check", "1")],
        }
        self._ports = {
            1: [RASPortRecord(1, "2", None, "ppp", None), RASPortRecord(1, "1", None, "ppp", None)],
            2: [],
        }
        self._pools = {
            1: [RASIPPoolRecord(12, 1, 8), RASIPPoolRecord(10, 1, 3)],
            2: [RASIPPoolRecord(20, 2, 4)],
        }

    def list(self):
        return list(self.records)

    def get(self, ras_id):
        return next((r for r in self.records if r.ras_id == ras_id), None)

    def attributes(self, ras_id):
        return list(self._attrs.get(ras_id, ()))

    def ports(self, ras_id):
        return list(self._ports.get(ras_id, ()))

    def ippools(self, ras_id):
        return list(self._pools.get(ras_id, ()))


def test_registry_loads_complete_ras_snapshot_in_source_order():
    repo = FakeRASRepository()
    registry = RASRuntimeRegistry(repo, lambda kind: {"type_default": kind})

    loaded = registry.reload()

    assert [ras.ras_id for ras in loaded] == [1, 2]
    ras = registry.get(1)
    assert ras is not None
    assert ras.attributes["online_check"] == "0"
    assert list(ras.ports) == ["2", "1"]
    assert ras.ippool_ids == (3, 8)
    assert ras.type_defaults == {"type_default": "Cisco"}


def test_registry_full_reload_removes_deleted_ras_state():
    repo = FakeRASRepository()
    registry = RASRuntimeRegistry(repo)
    registry.reload()

    repo.records = [repo.records[1]]
    registry.reload()

    assert registry.get(1) is None
    assert registry.get_by_ip("192.0.2.2").ras_id == 2


def test_registry_targeted_reload_removes_deactivated_ras():
    repo = FakeRASRepository()
    registry = RASRuntimeRegistry(repo)
    registry.reload()

    repo.records[0] = RASRecord(2, "router-2", "192.0.2.2", "Mikrotik", "s2", False, None)
    registry.reload(2)

    assert registry.get(2) is None
    assert registry.get(1) is not None


def test_registry_exposes_explicit_ras_attributes_to_access_consumers():
    repo = FakeRASRepository()
    registry = RASRuntimeRegistry(repo)
    registry.reload()
    assert registry.attributes(1) == [("online_check", "0"), ("ras_multi_login", "0")]
