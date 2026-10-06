from unittest.mock import Mock

from atd_radius.application.radius_runtime import NativeAccountingIdentityResolver, build_radius_dispatcher
from atd_radius.domain.radius import RadiusCode, RadiusPacket


def test_native_identity_resolver_maps_user_and_ras():
    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    ras = Mock()
    ras.get_by_ip.return_value = Mock(ras_id=3)

    resolver = NativeAccountingIdentityResolver(users, ras)

    assert resolver.user_id("alice") == 7
    assert resolver.ras_id("192.0.2.1") == 3


def test_build_radius_dispatcher_uses_native_access_context():
    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    users.attributes.return_value = []
    dispatcher = build_radius_dispatcher(users)

    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            4,
            {"User-Name": "alice", "User-Password": "secret"},
            b"0123456789abcdef",
        )
    )

    assert response.code is RadiusCode.ACCESS_ACCEPT
    assert "User-Password" not in response.attributes


def test_runtime_handler_applies_accounting_session():
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.radius_dispatch import DispatchResult

    dispatcher = Mock()
    event = AccountingEvent(AccountingStatus.START, "alice", "sid")
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 9, {}, b"0123456789abcdef"), event
    )
    sessions = Mock()
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3

    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)
    packet = RadiusPacket(RadiusCode.ACCOUNTING_REQUEST, 9, {"Acct-Status-Type": "Start"}, b"0123456789abcdef")

    response = handler(packet, ("192.0.2.1", 1812))

    assert response.code is RadiusCode.ACCOUNTING_RESPONSE
    sessions.apply.assert_called_once_with(event, 7, 3)


def test_session_views_exposes_only_active_runtime_sessions():
    from atd_radius.application.radius_runtime import session_views
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    registry = SessionRegistry()
    registry.start(SessionKey(7, 3, "active"))
    registry.start(SessionKey(7, 3, "stopped"))
    registry.stop(SessionKey(7, 3, "stopped"))

    views = session_views(registry)(7)

    assert tuple(view.unique_id for view in views) == ("active",)


def test_runtime_handler_can_attach_native_accounting_persistence():
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_session import AccountingSessionService
    from unittest.mock import Mock

    dispatcher = Mock()
    sessions = AccountingSessionService(Mock())
    identities = Mock()
    persistence = Mock()

    handler = RadiusRuntimeHandler(dispatcher, sessions, identities, persistence)

    assert handler.accounting_sessions.persistence is persistence


def test_build_ras_runtime_loads_and_binds_repository_change_hook():
    from atd_radius.application.radius_runtime import build_ras_runtime

    class Repo:
        on_change = None
        def __init__(self):
            self.records = []
        def list(self):
            return self.records
        def get(self, ras_id):
            return None
    repo = Repo()
    registry = build_ras_runtime(repo)
    assert registry.active() == ()
    assert repo.on_change == registry.on_repository_change


def test_build_radius_dispatcher_allocates_from_ras_bound_native_pool():
    from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry
    from atd_radius.domain.ras import RAS
    from atd_radius.infrastructure.ip_pool_repository import IPPoolRecord

    class PoolRepo:
        def list(self): return [IPPoolRecord(1, "pool-a", None)]
        def get(self, pool_id): return IPPoolRecord(1, "pool-a", None) if pool_id == 1 else None
        def list_addresses(self, pool_id): return ("192.0.2.20",)

    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    users.attributes.return_value = []
    ras = Mock()
    ras.get_by_ip.return_value = RAS(3, "192.0.2.1", "router", "Mikrotik", "secret", ippool_ids=(1,))
    ras.attributes.return_value = []

    pools = IPPoolRuntimeRegistry(PoolRepo())
    pools.reload()
    dispatcher = build_radius_dispatcher(users, ras=ras, ip_pools=pools)

    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            5,
            {"User-Name": "alice", "User-Password": "secret"},
            b"0123456789abcdef",
        ),
        source_ip="192.0.2.1",
    )

    assert response.code is RadiusCode.ACCESS_ACCEPT
    assert response.attributes["Framed-IP-Address"] == "192.0.2.20"
    assert response.attributes["Framed-IP-Netmask"] == "255.255.255.255"
    assert pools.get(1).used_ips == ("192.0.2.20",)
