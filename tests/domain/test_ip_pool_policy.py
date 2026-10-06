from atd_radius.domain.aaa import AAAAction, AAARequest
from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry, IPPoolFullError
from atd_radius.domain.ip_pool_policy import IPPoolAllocationPolicy
from atd_radius.infrastructure.ip_pool_repository import IPPoolRecord


class Repo:
    def __init__(self):
        self.records = [IPPoolRecord(1, "pool-a", None), IPPoolRecord(2, "pool-b", None)]
        self.addresses = {1: ("192.0.2.1",), 2: ("192.0.2.2",)}

    def list(self):
        return list(self.records)

    def get(self, pool_id):
        return next((record for record in self.records if record.pool_id == pool_id), None)

    def list_addresses(self, pool_id):
        return self.addresses.get(pool_id, ())


def runtime():
    registry = IPPoolRuntimeRegistry(Repo())
    registry.reload()
    return registry


def test_policy_uses_ras_pool_order_and_emits_native_reply_attributes():
    result = IPPoolAllocationPolicy(runtime()).evaluate(
        AAARequest("alice", {"__ras_ippool_ids": "2,1"})
    )
    assert result.action is AAAAction.ACCEPT
    assert result.attributes == {
        "Framed-IP-Address": "192.0.2.2",
        "Framed-IP-Netmask": "255.255.255.255",
    }


def test_policy_does_not_allocate_when_static_framed_ip_exists():
    registry = runtime()
    result = IPPoolAllocationPolicy(registry).evaluate(
        AAARequest("alice", {
            "__ras_ippool_ids": "1",
            "Framed-IP-Address": "192.0.2.100",
        })
    )
    assert result is None
    assert registry.get(1).used_ips == ()


def test_policy_rejects_when_all_bound_pools_are_exhausted():
    registry = runtime()
    registry.allocate(1)
    registry.allocate(2)
    result = IPPoolAllocationPolicy(registry).evaluate(
        AAARequest("alice", {"__ras_ippool_ids": "1,2"})
    )
    assert result.action is AAAAction.REJECT
    assert result.reason == "IP_POOL_EXHAUSTED"


def test_policy_does_not_allocate_if_authentication_pipeline_stops_before_it():
    registry = runtime()
    policy = IPPoolAllocationPolicy(registry)
    assert policy.evaluate(AAARequest("alice", {})) is None
    assert registry.get(1).used_ips == ()
