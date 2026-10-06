from __future__ import annotations

import pytest

from atd_radius.domain.ip_pool import (
    IPPoolFullError,
    IPPoolIPNotInUseError,
    IPPoolRuntimeRegistry,
)
from atd_radius.infrastructure.ip_pool_repository import IPPoolRecord


class FakeIPPoolRepository:
    def __init__(self):
        self.records = [
            IPPoolRecord(2, "pool-b", None),
            IPPoolRecord(1, "pool-a", "test"),
        ]
        self.addresses = {
            1: ["192.0.2.2", "192.0.2.1"],
            2: ["198.51.100.1"],
        }

    def list(self):
        return list(self.records)

    def get(self, pool_id):
        return next((record for record in self.records if record.pool_id == pool_id), None)

    def list_addresses(self, pool_id):
        return tuple(sorted(self.addresses.get(pool_id, ())))


def test_registry_allocates_in_address_order_and_tracks_used_state():
    registry = IPPoolRuntimeRegistry(FakeIPPoolRepository())
    registry.reload()

    assert registry.allocate(1) == "192.0.2.1"
    assert registry.allocate(1) == "192.0.2.2"
    with pytest.raises(IPPoolFullError):
        registry.allocate(1)


def test_claim_and_release_match_a124_runtime_semantics():
    registry = IPPoolRuntimeRegistry(FakeIPPoolRepository())
    registry.reload()

    registry.claim(1, "192.0.2.2")
    assert registry.get(1).used_ips == ("192.0.2.2",)
    registry.release(1, "192.0.2.2")
    assert registry.get(1).free_ips == ("192.0.2.1", "192.0.2.2")

    with pytest.raises(IPPoolIPNotInUseError):
        registry.release(1, "192.0.2.2")


def test_reload_preserves_used_ips_and_drops_deleted_members():
    repo = FakeIPPoolRepository()
    registry = IPPoolRuntimeRegistry(repo)
    registry.reload()
    registry.claim(1, "192.0.2.2")

    repo.addresses[1] = ["192.0.2.2", "192.0.2.3"]
    registry.reload(1)

    assert registry.get(1).used_ips == ("192.0.2.2",)
    assert registry.get(1).free_ips == ("192.0.2.3",)


def test_full_reload_removes_deleted_pools():
    repo = FakeIPPoolRepository()
    registry = IPPoolRuntimeRegistry(repo)
    registry.reload()
    repo.records = [repo.records[0]]
    registry.reload()
    assert registry.get(1) is None
    assert registry.get(2) is not None
