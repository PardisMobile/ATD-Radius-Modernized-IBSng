from types import SimpleNamespace

from atd_radius.application.radius_runtime import IPPoolSessionManager
from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry
from atd_radius.domain.ras import RASRuntimeRegistry
from atd_radius.infrastructure.ip_pool_repository import IPPoolRecord


class PoolRepo:
    def list(self):
        return [IPPoolRecord(1, "pool-a", None)]

    def get(self, pool_id):
        return IPPoolRecord(1, "pool-a", None) if pool_id == 1 else None

    def list_addresses(self, pool_id):
        return ("192.0.2.10", "192.0.2.11")


class RASRepo:
    on_change = None

    def list(self):
        return [SimpleNamespace(
            ras_id=7, description="router", ip="192.0.2.1", ras_type="Mikrotik",
            radius_secret="secret", active=True, comment=None,
        )]

    def get(self, ras_id):
        return self.list()[0] if ras_id == 7 else None

    def attributes(self, ras_id):
        return []

    def ports(self, ras_id):
        return []

    def ippools(self, ras_id):
        return [SimpleNamespace(serial=1, ras_id=7, ippool_id=1)]


def runtime():
    pools = IPPoolRuntimeRegistry(PoolRepo())
    pools.reload()
    ras = RASRuntimeRegistry(RASRepo())
    ras.reload()
    return pools, ras


def test_accounting_start_adopts_access_allocated_ip_and_stop_releases_it():
    pools, ras = runtime()
    pools.allocate(1)
    manager = IPPoolSessionManager(pools, ras)

    start = SimpleNamespace(remote_ip="192.0.2.10")
    manager.accounting_start(start, 7)
    assert pools.get(1).used_ips == ("192.0.2.10",)

    stop = SimpleNamespace(remote_ip="192.0.2.10")
    manager.accounting_stop(stop, 7)
    assert pools.get(1).used_ips == ()


def test_control_release_uses_session_ras_and_framed_ip():
    pools, ras = runtime()
    pools.allocate(1)
    manager = IPPoolSessionManager(pools, ras)

    class State:
        key = SimpleNamespace(ras_id=7)
        attributes = {"Framed-IP-Address": "192.0.2.10"}

    class Registry:
        def matching(self, attributes):
            return (State(),)

    manager.release_control({"Acct-Session-Id": "sid"}, Registry())
    assert pools.get(1).used_ips == ()
