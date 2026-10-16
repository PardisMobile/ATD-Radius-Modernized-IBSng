import pytest
from atd_radius.domain.ip_pool import IPAllocator,IPPool,IPPoolError

def test_allocator_starts_at_first_usable_host():
    pool=IPPool.from_cidr("test","10.20.30.0/30")
    assert str(IPAllocator(pool).allocate([]))=="10.20.30.1"

def test_allocator_skips_used_addresses():
    pool=IPPool.from_cidr("test","10.20.30.0/29")
    assert str(IPAllocator(pool).allocate(["10.20.30.1","10.20.30.2"]))=="10.20.30.3"

def test_allocator_reports_exhaustion():
    pool=IPPool.from_cidr("test","10.20.30.0/30")
    with pytest.raises(IPPoolError): IPAllocator(pool).allocate(["10.20.30.1","10.20.30.2"])

def test_disabled_pool_cannot_allocate():
    pool=IPPool.from_cidr("test","10.20.30.0/29",enabled=False)
    with pytest.raises(IPPoolError): pool.allocate()

def test_explicit_use_and_release_follow_a124_container_semantics():
    pool=IPPool.from_cidr("test","10.20.30.0/29")
    assert str(pool.use("10.20.30.4"))=="10.20.30.4"
    with pytest.raises(IPPoolError): pool.use("10.20.30.4")
    pool.release("10.20.30.4")
    assert pool.is_available("10.20.30.4")

def test_reply_uses_host_only_netmask():
    pool=IPPool.from_cidr("test","10.20.30.0/30")
    reply={}
    pool.set_in_reply(reply)
    assert reply["Framed-IP-Address"]=="10.20.30.1"
    assert reply["Framed-IP-Netmask"]=="255.255.255.255"



def test_pending_runtime_lease_is_adopted_by_matching_accounting_start():
    from types import SimpleNamespace
    from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry

    class Repository:
        def list(self):
            return [SimpleNamespace(pool_id=1, name="pool-a", comment=None)]
        def get(self, pool_id):
            return SimpleNamespace(pool_id=1, name="pool-a", comment=None) if pool_id == 1 else None
        def list_addresses(self, pool_id):
            return ("192.0.2.20",)

    registry = IPPoolRuntimeRegistry(Repository())
    registry.reload()
    ip = registry.allocate(1)
    registry.mark_pending(3, 1, ip, "alice", ttl_seconds=30)

    assert registry.consume_pending(3, ip, "alice") is True
    assert (3, ip) not in registry.pending_leases()
    assert ip in registry.get(1).used_ips


def test_pending_runtime_lease_expires_and_returns_address_to_pool():
    from types import SimpleNamespace
    from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry

    class Repository:
        def list(self):
            return [SimpleNamespace(pool_id=1, name="pool-a", comment=None)]
        def get(self, pool_id):
            return SimpleNamespace(pool_id=1, name="pool-a", comment=None) if pool_id == 1 else None
        def list_addresses(self, pool_id):
            return ("192.0.2.20", "192.0.2.21")

    registry = IPPoolRuntimeRegistry(Repository())
    registry.reload()
    ip = registry.allocate(1)
    registry.mark_pending(3, 1, ip, "alice", ttl_seconds=30)
    deadline = registry.pending_leases()[(3, ip)][2]

    assert registry.expire_pending(deadline) == 1
    assert ip not in registry.get(1).used_ips
    # A1.24 returns released addresses at the tail of the free queue.
    assert registry.allocate(1) == "192.0.2.21"


def test_pending_runtime_lease_cannot_be_adopted_by_another_username():
    from types import SimpleNamespace
    from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry

    class Repository:
        def list(self):
            return [SimpleNamespace(pool_id=1, name="pool-a", comment=None)]
        def get(self, pool_id):
            return SimpleNamespace(pool_id=1, name="pool-a", comment=None) if pool_id == 1 else None
        def list_addresses(self, pool_id):
            return ("192.0.2.20",)

    registry = IPPoolRuntimeRegistry(Repository())
    registry.reload()
    ip = registry.allocate(1)
    registry.mark_pending(3, 1, ip, "alice", ttl_seconds=30)

    assert registry.consume_pending(3, ip, "bob") is False
    assert (3, ip) in registry.pending_leases()
    assert ip in registry.get(1).used_ips
    assert registry.release_pending(3, ip) is True
    assert ip not in registry.get(1).used_ips
