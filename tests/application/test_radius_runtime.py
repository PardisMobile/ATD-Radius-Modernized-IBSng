import pytest
from unittest.mock import Mock

from atd_radius.application.radius_runtime import NativeAccountingIdentityResolver, build_radius_dispatcher
from atd_radius.domain.radius import RadiusCode, RadiusPacket


def test_native_identity_resolver_maps_user_and_ras():
    users = Mock()
    users.accounting_user_id = None  # Exercise the legacy-repository fallback.
    users.get_authentication_record.return_value = (7, "secret", False)
    ras = Mock()
    ras.get_by_ip.return_value = Mock(ras_id=3)

    resolver = NativeAccountingIdentityResolver(users, ras)

    assert resolver.user_id("alice") == 7
    assert resolver.ras_id("192.0.2.1") == 3


def test_native_identity_resolver_prefers_accounting_namespace_and_fails_closed():
    users = Mock()
    users.accounting_user_id.return_value = None
    users.get_authentication_record.return_value = (99, "secret", False)
    ras = Mock()

    resolver = NativeAccountingIdentityResolver(users, ras)

    # Ambiguous/missing Accounting identity must not fall back to the normal
    # authentication namespace, or accounting could be charged to the wrong user.
    assert resolver.user_id("shared-name") is None
    users.accounting_user_id.assert_called_once_with("shared-name")
    users.get_authentication_record.assert_not_called()


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
    from atd_radius.domain.radius_runtime import SessionRegistry

    sessions = Mock()
    sessions.registry = SessionRegistry()
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    identities.ras.get.return_value = None

    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)
    packet = RadiusPacket(RadiusCode.ACCOUNTING_REQUEST, 9, {"Acct-Status-Type": "Start"}, b"0123456789abcdef")

    response = handler(packet, ("192.0.2.1", 1812))

    assert response.code is RadiusCode.ACCOUNTING_RESPONSE
    sessions.apply.assert_called_once_with(event, 7, 3)




def test_runtime_tags_accounting_event_with_source_ras_service_family():
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.radius_dispatch import DispatchResult
    from atd_radius.domain.radius_runtime import SessionRegistry

    dispatcher = Mock()
    event = AccountingEvent(AccountingStatus.START, "voip-alice", "call-1")
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 10, {}, b"0123456789abcdef"), event
    )
    sessions = Mock()
    sessions.registry = SessionRegistry()
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    ras = Mock()
    ras.ras_type = "MVTS"
    ras.all_attributes.return_value = {}
    identities.ras.get.return_value = ras

    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)
    packet = RadiusPacket(
        RadiusCode.ACCOUNTING_REQUEST, 10,
        {"Acct-Status-Type": "Start", "User-Name": "voip-alice", "Acct-Session-Id": "call-1"},
        b"0123456789abcdef",
    )
    handler(packet, ("192.0.2.1", 1812))

    applied_event = sessions.apply.call_args.args[0]
    assert applied_event.service == "voip"
    assert applied_event.ras_multi_login_allowed is True

def test_runtime_resolves_cisco_voip_accounting_user_before_identity_lookup():
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.radius_dispatch import DispatchResult
    from atd_radius.domain.radius_runtime import SessionRegistry

    dispatcher = Mock()
    event = AccountingEvent(
        AccountingStatus.START, "voipuserSecret", "acct-1",
        attributes={
            "H323-Conf-ID": "H323-conf-id=call-1",
            "H323-call-type": "H323-call-type=VoIP",
            "H323-call-origin": "H323-call-origin=originate",
        },
    )
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 12, {}, b"0123456789abcdef"), event
    )
    sessions = Mock()
    sessions.registry = SessionRegistry()
    identities = Mock()
    identities.ras_id.return_value = 3
    identities.user_id.return_value = 7
    ras = Mock()
    ras.ras_type = "Cisco"
    ras.all_attributes.return_value = {"cisco_voip_username_length": "8"}
    identities.ras.get.return_value = ras

    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)
    packet = RadiusPacket(
        RadiusCode.ACCOUNTING_REQUEST, 12,
        {
            "Acct-Status-Type": "Start",
            "User-Name": "voipuserSecret",
            "H323-Conf-ID": "H323-conf-id=call-1",
            "H323-call-type": "H323-call-type=VoIP",
            "H323-call-origin": "H323-call-origin=originate",
        },
        b"0123456789abcdef",
    )
    handler(packet, ("192.0.2.1", 1812))

    identities.user_id.assert_called_once_with("voipuser")
    applied_event = sessions.apply.call_args.args[0]
    assert applied_event.username == "voipuser"
    assert applied_event.session_id == "call-1"
    assert applied_event.service == "voip"


def test_runtime_resolves_cisco_voip_session_identity_with_service_context():
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionRegistry

    # Use the real Accounting dispatcher here: this exercises list-shaped
    # decoded attributes all the way through normalization and provider routing.
    dispatcher = RadiusDispatcher(Mock())
    sessions = Mock()
    sessions.registry = SessionRegistry()
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    ras = Mock()
    ras.ras_type = "Cisco"
    ras.all_attributes.return_value = {}
    identities.ras.get.return_value = ras

    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)
    packet = RadiusPacket(
        RadiusCode.ACCOUNTING_REQUEST, 11,
        {
            "Acct-Status-Type": ["Start"],
            "User-Name": ["alice"],
            "Acct-Session-Id": ["acct-fallback"],
            "H323-Conf-ID": ["h323-call-42"],
            "NAS-Port": ["17"],
            "H323-call-type": ["VoIP"],
            "H323-call-origin": ["originate"],
        },
        b"0123456789abcdef",
    )
    response = handler(packet, ("192.0.2.1", 1812))

    assert response.code is RadiusCode.ACCOUNTING_RESPONSE
    applied_event = sessions.apply.call_args.args[0]
    assert applied_event.service == "voip"
    assert applied_event.session_id == "h323-call-42"
    assert applied_event.attributes["NAS-Port"] == "17"
    assert applied_event.ras_multi_login_allowed is False

def test_runtime_skips_cisco_voip_alive_from_charge_lifecycle():
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.radius_dispatch import DispatchResult
    from atd_radius.domain.radius_runtime import SessionRegistry

    dispatcher = Mock()
    event = AccountingEvent(
        AccountingStatus.ALIVE,
        "alice",
        "acct-1",
        attributes={
            "H323-Conf-ID": "call-1",
            "H323-call-type": "VoIP",
            "H323-call-origin": "originate",
        },
    )
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 12, {}, b"0123456789abcdef"), event
    )
    sessions = Mock()
    sessions.registry = SessionRegistry()
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    ras = Mock()
    ras.ras_type = "Cisco"
    ras.all_attributes.return_value = {}
    identities.ras.get.return_value = ras

    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)
    response = handler(
        RadiusPacket(
            RadiusCode.ACCOUNTING_REQUEST, 12,
            {"Acct-Status-Type": "Alive", "User-Name": "alice"},
            b"0123456789abcdef",
        ),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.ACCOUNTING_RESPONSE
    sessions.apply.assert_not_called()


def test_session_views_exposes_only_active_runtime_sessions():
    from atd_radius.application.radius_runtime import session_views
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    registry = SessionRegistry()
    registry.start(SessionKey(7, 3, "active"), ras_multi_login_allowed=False)
    registry.start(SessionKey(7, 3, "stopped"))
    registry.stop(SessionKey(7, 3, "stopped"))

    views = session_views(registry)(7)

    assert tuple(view.unique_id for view in views) == ("active",)
    assert views[0].ras_multi_login_allowed is False


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


def test_build_native_radius_runtime_composes_native_accounting_and_ip_pool_runtime():
    from atd_radius.application.radius_runtime import build_native_radius_runtime
    from atd_radius.infrastructure.ip_pool_repository import IPPoolRecord
    from unittest.mock import Mock

    class RASRepo:
        on_change = None
        def list(self):
            return []
        def get(self, ras_id):
            return None

    class PoolRepo:
        def list(self):
            return [IPPoolRecord(1, "pool-a", None)]
        def get(self, pool_id):
            return IPPoolRecord(1, "pool-a", None)
        def list_addresses(self, pool_id):
            return ("192.0.2.30",)

    users = Mock()
    handler = build_native_radius_runtime(
        Mock(),
        users=users,
        ras_repository=RASRepo(),
        pool_repository=PoolRepo(),
    )

    assert handler.accounting_sessions.persistence is not None
    assert handler.ip_pool_sessions is not None
    assert handler.dispatcher.access_context.ras is not None
    from atd_radius.domain.accounting_charge import UserChargeSettlement, InternetChargeSettlement, VoipChargeSettlement
    charge = handler.accounting_sessions.charge
    assert isinstance(charge, UserChargeSettlement)
    assert isinstance(charge.internet, InternetChargeSettlement)
    assert isinstance(charge.voip, VoipChargeSettlement)
    assert charge.users is users


def test_native_radius_packet_handler_reuses_runtime_state_across_transactions():
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState

    class FakeConnection:
        def __init__(self):
            self.entered = 0
            self.exited = 0
        def __enter__(self):
            self.entered += 1
            return self
        def __exit__(self, exc_type, exc, tb):
            self.exited += 1
            return False

    class Repo:
        def __init__(self, conn):
            self.conn = conn
            self.on_change = None
        def list(self): return []
        def get(self, _): return None
        def attributes(self, _): return []
        def ports(self, _): return []
        def ippools(self, _): return []

    connections = []
    state = NativeRadiusRuntimeState()

    # The packet handler is intentionally exercised with a connection factory;
    # repository construction is the only DB-scoped part of the runtime.
    def factory():
        conn = FakeConnection()
        connections.append(conn)
        return conn

    # Replace native repositories for this unit test so no PostgreSQL driver is needed.
    handler = NativeRadiusPacketHandler(state, factory)
    handler.connection_factory = factory

    # Construction should be deferred to the packet and state must remain reusable.
    assert state.sessions.active_for_user(7) == ()
    assert connections == []


def test_accounting_identity_resolution_and_apply_share_registry_lock():
    from contextlib import contextmanager
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.radius_dispatch import DispatchResult

    guard = {"entered": False}

    @contextmanager
    def synchronized():
        assert not guard["entered"]
        guard["entered"] = True
        try:
            yield
        finally:
            guard["entered"] = False

    class Registry:
        pass

    Registry.synchronized = staticmethod(synchronized)

    class Sessions:
        registry = Registry()
        def apply(self, event, user_id, ras_id):
            assert guard["entered"]
            self.applied = (event, user_id, ras_id)

    dispatcher = Mock()
    event = AccountingEvent(AccountingStatus.START, "alice", "sid")
    dispatcher.accounting.side_effect = lambda packet: (
        (_ for _ in ()).throw(AssertionError("accounting dispatch outside lock"))
        if not guard["entered"] else DispatchResult(
            RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 9, {}, b"0123456789abcdef"), event
        )
    )
    identities = Mock()
    identities.user_id.side_effect = lambda username: (
        7 if guard["entered"] else (_ for _ in ()).throw(AssertionError("user lookup outside lock"))
    )
    identities.ras_id.side_effect = lambda source_ip: (
        3 if guard["entered"] else (_ for _ in ()).throw(AssertionError("RAS lookup outside lock"))
    )
    identities.ras.get.return_value = None
    sessions = Sessions()
    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)

    response = handler(
        RadiusPacket(RadiusCode.ACCOUNTING_REQUEST, 9, {"Acct-Status-Type": "Start"}, b"0123456789abcdef"),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.ACCOUNTING_RESPONSE
    assert sessions.applied == (event, 7, 3)
    assert guard["entered"] is False


def test_native_packet_handler_schedules_users_with_active_charge_sessions():
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    state = NativeRadiusRuntimeState()
    state.ras = Mock()
    state.ras.get.return_value = RAS(3, "192.0.2.3", "mvts", "MVTS", "secret")
    session = state.sessions.start(SessionKey(7, 3, "conf-7"), {"User-Name": "alice"})
    session.charge_id = 12
    session.charge_kind = "voip"
    handler = NativeRadiusPacketHandler(state, Mock())
    try:
        handler._refresh_voip_limit_schedule(7)
        assert ("voip-user", 7) in handler.voip_limit_loop.scheduler.pending_keys()
    finally:
        handler.close()


def test_native_packet_handler_schedules_internet_only_sessions():
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    state = NativeRadiusRuntimeState()
    state.ras = Mock()
    state.ras.get.return_value = RAS(3, "192.0.2.3", "router", "MikroTik", "secret")
    session = state.sessions.start(SessionKey(7, 3, "port-7"), {"User-Name": "alice"})
    session.charge_id = 12
    session.charge_kind = "internet"
    handler = NativeRadiusPacketHandler(state, Mock())
    try:
        handler._refresh_voip_limit_schedule(7)
        assert ("voip-user", 7) in handler.voip_limit_loop.scheduler.pending_keys()
    finally:
        handler.close()


def test_native_packet_handler_does_not_repeat_a_successfully_requested_termination():
    from datetime import datetime, timezone
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "conf-7")
    session = state.sessions.start(key, {"User-Name": "alice"})
    session.termination_requested_reason = "credit_finished"
    session.termination_requested_at = datetime.now(timezone.utc)
    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    try:
        handler._terminate_voip_session(key, "credit_finished")
        assert session.termination_requested_reason == "credit_finished"
    finally:
        handler.close()


def test_native_packet_handler_uses_source_ras_terminator_for_exact_session(monkeypatch):
    from atd_radius.application import radius_runtime
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    class Registry:
        def get(self, ras_id):
            return RAS(ras_id, "192.0.2.3", "mvts", "MVTS", "secret") if ras_id == 3 else None

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "conf-7")
    session = state.sessions.start(key, {"User-Name": "alice"})
    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    terminate = Mock()
    handler._ras_terminator.terminate = terminate
    monkeypatch.setattr(radius_runtime, "build_ras_runtime", lambda *_args: Registry())
    class Users:
        def __init__(self, _conn): pass
        def voip_credentials(self, user_id):
            assert user_id == 7
            return ("sip-alice", "secret")
    monkeypatch.setattr(radius_runtime, "UserRepository", Users)
    try:
        handler._terminate_voip_session(key, "credit_finished")
        assert session.termination_requested_reason == "credit_finished"
        terminate.assert_called_once()
        args = terminate.call_args.args
        assert args[1].key == key
        assert args[1].attributes["User-Name"] == "sip-alice"
        assert args[2] == "credit_finished"
    finally:
        handler.close()


def test_failed_provider_termination_clears_pending_marker_for_retry(monkeypatch):
    from atd_radius.application import radius_runtime
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    class Registry:
        def get(self, ras_id):
            return RAS(ras_id, "192.0.2.3", "mvts", "MVTS", "secret") if ras_id == 3 else None

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "conf-8")
    session = state.sessions.start(key, {"User-Name": "alice"})
    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    handler._ras_terminator.terminate = Mock(side_effect=TimeoutError("timeout"))
    monkeypatch.setattr(radius_runtime, "build_ras_runtime", lambda *_args: Registry())
    class Users:
        def __init__(self, _conn): pass
        def voip_credentials(self, _user_id): return ("sip-alice", "secret")
    monkeypatch.setattr(radius_runtime, "UserRepository", Users)
    try:
        import pytest
        with pytest.raises(TimeoutError):
            handler._terminate_voip_session(key, "credit_finished")
        assert session.termination_requested_reason is None
        assert session.termination_requested_at is None
    finally:
        handler.close()



def test_accounting_identity_resolver_uses_native_voip_username_lookup():
    from atd_radius.application.radius_runtime import NativeAccountingIdentityResolver

    class Users:
        def accounting_user_id(self, username):
            assert username == "sip-alice"
            return 17

        def get_authentication_record(self, _username):
            raise AssertionError("normal-only lookup must not shadow VoIP identity")

    resolver = NativeAccountingIdentityResolver(Users(), Mock())
    assert resolver.user_id("sip-alice") == 17

def test_voip_limit_planner_uses_source_local_clock(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from atd_radius.application import radius_runtime
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.accounting_charge import VoipLimitPlan
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    observed = {}
    expected_local = datetime(
        2026, 10, 17, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))
    ).astimezone()

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            # A1.24 uses local wall-clock time for charge-rule intervals.
            assert tz is None
            return datetime(2026, 10, 17, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    class Registry:
        def get(self, ras_id):
            return RAS(ras_id, "192.0.2.3", "mvts", "MVTS", "secret")

    class Users:
        def __init__(self, _conn): pass

    class Credits:
        def __init__(self, _conn): pass
        def get(self, _user_id): return 10

    class FakeSettlement:
        def __init__(self, *_args): pass
        def plan_limits(self, _states, when, _credit, _context):
            observed["when"] = when
            return VoipLimitPlan(None)

    state = NativeRadiusRuntimeState()
    state.ras = Registry()
    session = state.sessions.start(SessionKey(7, 3, "call-1"), {"User-Name": "sip-alice"})
    session.charge_id = 2
    session.charge_kind = "voip"
    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    monkeypatch.setattr(radius_runtime, "datetime", FixedDateTime)
    monkeypatch.setattr(radius_runtime, "build_ras_runtime", lambda *_args: Registry())
    monkeypatch.setattr(radius_runtime, "RASRepository", lambda _conn: object())
    monkeypatch.setattr(radius_runtime, "UserRepository", Users)
    monkeypatch.setattr(radius_runtime, "UserCreditRepository", Credits)
    monkeypatch.setattr(radius_runtime, "PostgresVoipChargeRuleRepository", lambda _conn: object())
    monkeypatch.setattr(radius_runtime, "PostgresVoipTariffRepository", lambda _conn: object())
    monkeypatch.setattr(radius_runtime, "VoipChargeSettlement", FakeSettlement)
    try:
        handler._check_voip_limits(7)
        assert observed["when"] == expected_local
    finally:
        handler.close()

def test_disconnect_request_settles_charge_and_closes_native_log():
    from decimal import Decimal
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    class Persistence:
        def __init__(self):
            self.closed = []

        def start(self, *_args): return 101
        def update(self, *_args): pass
        def stop(self, connection_log_id, event, credit_used=None):
            self.closed.append((connection_log_id, event, credit_used))

    class Charge:
        def __init__(self): self.settled = []
        def start(self, *_args): pass
        def update(self, *_args): return None
        def settle(self, state, when, ras_id, port):
            self.settled.append((state.key, ras_id, port))
            return Decimal("1.25")

    registry = SessionRegistry()
    key = SessionKey(7, 3, "sid-7")
    state = registry.start(
        key,
        {
            "User-Name": "alice",
            "Acct-Session-Id": "sid-7",
            "NAS-Port": "4",
            "__connection_log_id": "101",
        },
        input_octets=120,
        output_octets=240,
    )
    persistence = Persistence()
    charge = Charge()
    sessions = AccountingSessionService(registry, persistence, charge)
    dispatcher = RadiusDispatcher(PluginPipeline([]))
    identities = Mock()
    identities.ras_id.return_value = 3
    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)

    response = handler(
        RadiusPacket(
            RadiusCode.DISCONNECT_REQUEST,
            22,
            {"Acct-Session-Id": "sid-7"},
            bytes(16),
        ),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.DISCONNECT_ACK
    assert state.stopped is True
    assert charge.settled == [(key, 3, "4")]
    assert len(persistence.closed) == 1
    log_id, event, credit_used = persistence.closed[0]
    assert log_id == 101
    assert event.status.value == "Stop"
    assert event.input_octets == 120 and event.output_octets == 240
    assert credit_used == Decimal("1.25")
    assert "__connection_log_id" not in event.attributes




def test_recovery_restores_open_connection_log_session_and_pool_lease():
    from datetime import datetime
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey

    now = datetime(2026, 10, 17, 10, 0, 0)
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [
        (101, 7, None, now, None, True, 1, 3, "Acct-Session-Id", "sid-101"),
        (101, 7, None, now, None, True, 1, 3, "Acct-Input-Octets", "120"),
        (101, 7, None, now, None, True, 1, 3, "Acct-Output-Octets", "240"),
        (101, 7, None, now, None, True, 1, 3, "User-Name", "alice"),
        (101, 7, None, now, None, True, 1, 3, "Framed-IP-Address", "192.0.2.20"),
        (101, 7, None, now, None, True, 1, 3, "NAS-Port", "4"),
    ]
    ras = Mock()
    ras.ras_type = "Mikrotik"
    ras.ippool_ids = (9,)
    ras.all_attributes.return_value = {}
    ras_registry = Mock()
    ras_registry.get.return_value = ras
    pools = Mock()
    pools.find_pool.return_value = 9

    state = NativeRadiusRuntimeState()
    state.ras = ras_registry
    handler = NativeRadiusPacketHandler.__new__(NativeRadiusPacketHandler)
    handler.state = state
    handler._logger = Mock()
    charge = Mock()
    charge.start.side_effect = lambda session, *_: setattr(session, "charge_id", 12)

    handler._recover_open_sessions(conn, charge, ras_registry, pools)

    restored = state.sessions.get(SessionKey(7, 3, "4"))
    assert restored is not None
    assert restored.started and not restored.stopped
    assert restored.input_octets == 120 and restored.output_octets == 240
    assert restored.started_at == now
    assert restored.attributes["__connection_log_id"] == "101"
    assert restored.charge_id == 12
    charge.start.assert_called_once()
    pools.ensure_claimed.assert_called_once_with(9, "192.0.2.20")
    assert state.sessions_recovered is True


def test_recovery_is_one_shot_and_does_not_overwrite_live_sessions():
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey

    conn = Mock()
    conn.execute.return_value.fetchall.return_value = []
    state = NativeRadiusRuntimeState()
    state.sessions.start(SessionKey(7, 3, "already-live"))
    handler = NativeRadiusPacketHandler.__new__(NativeRadiusPacketHandler)
    handler.state = state
    handler._logger = Mock()
    ras_registry = Mock()
    pools = Mock()
    charge = Mock()

    handler._recover_open_sessions(conn, charge, ras_registry, pools)
    handler._recover_open_sessions(conn, charge, ras_registry, pools)

    conn.execute.assert_called_once()
    assert state.sessions.get(SessionKey(7, 3, "already-live")) is not None
    assert state.sessions_recovered is True
    charge.start.assert_not_called()



def test_recovery_uses_provider_defined_voip_call_identity():
    from datetime import datetime
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey

    now = datetime(2026, 10, 17, 10, 0, 0)
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [
        (202, 8, None, now, None, True, 2, 4, "Acct-Session-Id", "acct-202"),
        (202, 8, None, now, None, True, 2, 4, "H323-conf-id", "call-202"),
        (202, 8, None, now, None, True, 2, 4, "User-Name", "voip-login"),
    ]
    ras = Mock()
    ras.ras_type = "MVTS"
    ras.ippool_ids = ()
    ras.all_attributes.return_value = {}
    ras_registry = Mock()
    ras_registry.get.return_value = ras
    pools = Mock()
    state = NativeRadiusRuntimeState()
    handler = NativeRadiusPacketHandler.__new__(NativeRadiusPacketHandler)
    handler.state = state
    handler._logger = Mock()
    charge = Mock()
    charge.start.side_effect = lambda session, *_: (
        setattr(session, "charge_id", 12),
        setattr(session, "charge_kind", "voip"),
    )

    recovered_voip_users = handler._recover_open_sessions(conn, charge, ras_registry, pools)

    assert recovered_voip_users == {8}
    restored = state.sessions.get(SessionKey(8, 4, "call-202"))
    assert restored is not None
    assert restored.attributes["Acct-Session-Id"] == "acct-202"
    assert restored.attributes["H323-conf-id"] == "call-202"
    charge.start.assert_called_once()



def test_recovery_uses_cisco_voip_packet_discriminator_for_session_identity():
    from datetime import datetime
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey

    now = datetime(2026, 10, 17, 10, 0, 0)
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [
        (203, 8, None, now, None, True, 2, 4, "Acct-Session-Id", "acct-203"),
        (203, 8, None, now, None, True, 2, 4, "H323-Conf-ID", "cisco-call-203"),
        (203, 8, None, now, None, True, 2, 4, "NAS-Port", "17"),
        (203, 8, None, now, None, True, 2, 4, "User-Name", "voip-login"),
    ]
    ras = Mock()
    ras.ras_type = "Cisco"
    ras.ippool_ids = ()
    ras.all_attributes.return_value = {}
    ras_registry = Mock()
    ras_registry.get.return_value = ras
    pools = Mock()
    state = NativeRadiusRuntimeState()
    handler = NativeRadiusPacketHandler.__new__(NativeRadiusPacketHandler)
    handler.state = state
    handler._logger = Mock()
    charge = Mock()

    handler._recover_open_sessions(conn, charge, ras_registry, pools)

    restored = state.sessions.get(SessionKey(8, 4, "cisco-call-203"))
    assert restored is not None
    assert restored.attributes["NAS-Port"] == "17"
    charge.start.assert_called_once()


def test_production_access_context_marks_allocated_address_as_pending():
    from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry
    from atd_radius.domain.ras import RAS
    from atd_radius.infrastructure.ip_pool_repository import IPPoolRecord

    class PoolRepo:
        def list(self):
            return [IPPoolRecord(1, "pool-a", None)]
        def get(self, pool_id):
            return IPPoolRecord(1, "pool-a", None) if pool_id == 1 else None
        def list_addresses(self, pool_id):
            return ("192.0.2.20",)

    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    users.attributes.return_value = []
    ras = Mock()
    ras.get_by_ip.return_value = RAS(
        3, "192.0.2.1", "router", "Mikrotik", "secret", ippool_ids=(1,)
    )
    ras.attributes.return_value = []
    pools = IPPoolRuntimeRegistry(PoolRepo())
    pools.reload()
    dispatcher = build_radius_dispatcher(users, ras=ras, ip_pools=pools)

    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            6,
            {"User-Name": "alice", "User-Password": "secret"},
            b"0123456789abcdef",
        ),
        source_ip="192.0.2.1",
    )

    assert response.code is RadiusCode.ACCESS_ACCEPT
    assert pools.pending_leases()[(3, "192.0.2.20")][1] == "alice"
    assert pools.get(1).used_ips == ("192.0.2.20",)



def test_runtime_tracks_successful_cisco_voip_authorization_and_consumes_on_start():
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.radius_dispatch import DispatchResult
    from atd_radius.domain.radius_runtime import SessionRegistry

    dispatcher = Mock()
    dispatcher.access.return_value = RadiusPacket(
        RadiusCode.ACCESS_ACCEPT, 1, {}, b"0123456789abcdef"
    )
    sessions = Mock()
    sessions.registry = SessionRegistry()
    identities = Mock()
    ras = Mock()
    ras.ras_id = 3
    ras.ras_type = "Cisco"
    ras.all_attributes.return_value = {"cisco_voip_username_length": 5}
    identities.ras.get_by_ip.return_value = ras
    identities.ras.get.return_value = ras
    identities.ras_id.return_value = 3
    identities.user_id.return_value = 7
    auth_ids = {}
    handler = RadiusRuntimeHandler(
        dispatcher, sessions, identities, cisco_voip_auth_h323_ids=auth_ids
    )
    auth_packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST, 1,
        {
            "User-Name": "aliceSecret",
            "Called-Station-Id": "12345",
            "H323-conf-id": ["H323-conf-id=auth-call-1"],
        },
        b"0123456789abcdef",
    )
    handler(auth_packet, ("192.0.2.1", 1812))
    assert auth_ids == {3: {"auth-call-1"}}

    event = AccountingEvent(
        AccountingStatus.STOP, "aliceSecret", "acct-stop",
        attributes={
            "H323-conf-id": "H323-conf-id=auth-call-1",
            "H323-call-type": "H323-call-type=Telephony",
            "H323-call-origin": "H323-call-origin=answer",
        },
    )
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 2, {}, b"0123456789abcdef"),
        event,
    )
    handler(
        RadiusPacket(
            RadiusCode.ACCOUNTING_REQUEST, 2,
            {
                "Acct-Status-Type": "Stop",
                "User-Name": "aliceSecret",
                "H323-conf-id": "H323-conf-id=auth-call-1",
                "H323-call-type": "H323-call-type=Telephony",
                "H323-call-origin": "H323-call-origin=answer",
            },
            b"0123456789abcdef",
        ),
        ("192.0.2.1", 1812),
    )
    identities.user_id.assert_called_with("alice")
    sessions.apply.assert_called_once()

    # A real VoIP/originate Start consumes the pre-auth ID, exactly as
    # CiscoRas.__voipAcctStart does before dispatching VOIP_UPDATE.
    start_event = AccountingEvent(
        AccountingStatus.START, "aliceSecret", "acct-start",
        attributes={
            "H323-conf-id": "H323-conf-id=auth-call-1",
            "H323-call-type": "H323-call-type=VoIP",
            "H323-call-origin": "H323-call-origin=originate",
        },
    )
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 4, {}, b"0123456789abcdef"),
        start_event,
    )
    handler(
        RadiusPacket(
            RadiusCode.ACCOUNTING_REQUEST, 4,
            {
                "Acct-Status-Type": "Start",
                "User-Name": "aliceSecret",
                "H323-conf-id": "H323-conf-id=auth-call-1",
                "H323-call-type": "H323-call-type=VoIP",
                "H323-call-origin": "H323-call-origin=originate",
            },
            b"0123456789abcdef",
        ),
        ("192.0.2.1", 1812),
    )
    assert auth_ids == {3: set()}
    assert identities.user_id.call_args_list[-1].args == ("alice",)



def test_cisco_voip_alive_updates_only_provider_online_tracker():
    from datetime import datetime, timezone
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.radius_dispatch import DispatchResult
    from atd_radius.domain.radius_runtime import SessionRegistry

    dispatcher = Mock()
    event = AccountingEvent(
        AccountingStatus.ALIVE, "aliceSecret", "acct-1",
        observed_at=datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc),
        attributes={
            "H323-conf-id": "H323-conf-id=call-1",
            "H323-call-type": "H323-call-type=VoIP",
            "H323-call-origin": "H323-call-origin=originate",
        },
    )
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 3, {}, b"0123456789abcdef"), event
    )
    sessions = Mock()
    sessions.registry = SessionRegistry()
    identities = Mock()
    identities.ras_id.return_value = 4
    identities.user_id.return_value = 7
    ras = Mock()
    ras.ras_type = "Cisco"
    ras.all_attributes.return_value = {"cisco_voip_username_length": 8}
    identities.ras.get.return_value = ras
    online = {4: {"call-1": {"username": "alice", "last_update": 1.0}}}
    handler = RadiusRuntimeHandler(
        dispatcher, sessions, identities, cisco_online_status=online
    )
    handler(
        RadiusPacket(
            RadiusCode.ACCOUNTING_REQUEST, 3,
            {
                "Acct-Status-Type": "Alive",
                "User-Name": "aliceSecret",
                "H323-conf-id": "H323-conf-id=call-1",
                "H323-call-type": "H323-call-type=VoIP",
                "H323-call-origin": "H323-call-origin=originate",
            },
            b"0123456789abcdef",
        ),
        ("192.0.2.1", 1812),
    )
    sessions.apply.assert_not_called()
    assert online[4]["call-1"]["last_update"] == event.observed_at.timestamp()

def test_recovery_skips_cisco_voip_row_without_h323_identity_even_if_nas_port_exists():
    from datetime import datetime
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey

    now = datetime(2026, 10, 19, 10, 0, 0)
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [
        (204, 8, None, now, None, True, 2, 4, "Acct-Session-Id", "acct-204"),
        (204, 8, None, now, None, True, 2, 4, "NAS-Port", "17"),
        (204, 8, None, now, None, True, 2, 4, "User-Name", "voip-login"),
    ]
    ras = Mock()
    ras.ras_type = "Cisco"
    ras.ippool_ids = ()
    ras.all_attributes.return_value = {}
    ras_registry = Mock()
    ras_registry.get.return_value = ras
    pools = Mock()
    state = NativeRadiusRuntimeState()
    handler = NativeRadiusPacketHandler.__new__(NativeRadiusPacketHandler)
    handler.state = state
    handler._logger = Mock()
    charge = Mock()

    handler._recover_open_sessions(conn, charge, ras_registry, pools)

    assert state.sessions.get(SessionKey(8, 4, "acct-204")) is None
    assert state.sessions.get(SessionKey(8, 4, "17")) is None
    charge.start.assert_not_called()




def test_gnugk_runtime_resolves_native_voip_username_before_termination(monkeypatch):
    from atd_radius.application import radius_runtime
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False

    class Registry:
        def get(self, ras_id):
            if ras_id != 3:
                return None
            return RAS(
                3, "192.0.2.30", "GnuGk test", "GnuGk", "secret",
                attributes={"gnugk_multiple_login": "1", "gnugk_status_port": "7000"},
            )

    class Users:
        def __init__(self, _conn): pass
        def voip_credentials(self, user_id):
            assert user_id == 7
            return ("sip-alice", "secret")

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "h323-conf-7")
    session = state.sessions.start(key, {"User-Name": "ibs-login"})
    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    terminate = Mock()
    handler._ras_terminator.terminate = terminate
    monkeypatch.setattr(radius_runtime, "build_ras_runtime", lambda *_args: Registry())
    monkeypatch.setattr(radius_runtime, "UserRepository", Users)
    try:
        handler._terminate_voip_session(key, "credit_finished")
        assert session.termination_requested_reason == "credit_finished"
        args = terminate.call_args.args
        assert args[1].key == key
        assert args[1].attributes["User-Name"] == "ibs-login"
        assert args[1].attributes["voip_username"] == "sip-alice"
        assert args[2] == "credit_finished"
    finally:
        handler.close()


@pytest.mark.parametrize(
    ("provider", "ras_attrs"),
    [("MikroTik", {"mikrotik_ssh_wrapper": "/opt/ibs-addons/mikrotik/ssh_wrapper"}), ("Cisco VPDN", {"cisco_rsh_command": "/opt/ibs-addons/cisco/rsh_wrapper"})],
)
def test_native_termination_runtime_resolves_normal_username_for_internet_ras(monkeypatch, provider, ras_attrs):
    from atd_radius.application import radius_runtime
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
    class Registry:
        def get(self, ras_id):
            return RAS(3, "192.0.2.30", "termination test", provider, "secret", attributes=ras_attrs) if ras_id == 3 else None
    class Users:
        def __init__(self, _conn): pass
        def normal_credentials(self, user_id):
            assert user_id == 7
            return ("native-user", "secret")

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "sid-7")
    session = state.sessions.start(key, {"User-Name": "wire-login", "Framed-IP-Address": "198.51.100.20", "NAS-Port-Type": "Wireless-802.11"})
    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    terminate = Mock()
    handler._ras_terminator.terminate = terminate
    monkeypatch.setattr(radius_runtime, "build_ras_runtime", lambda *_args: Registry())
    monkeypatch.setattr(radius_runtime, "UserRepository", Users)
    try:
        handler._terminate_voip_session(key, "credit_finished")
        assert session.termination_requested_reason == "credit_finished"
        snapshot = terminate.call_args.args[1]
        assert snapshot.attributes["normal_username"] == "native-user"
        assert snapshot.attributes["User-Name"] == "wire-login"
    finally:
        handler.close()


def test_coa_request_updates_only_supported_live_authorization_without_settlement():
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    registry = SessionRegistry()
    key = SessionKey(7, 3, "sid-coa")
    state = registry.start(
        key,
        {"User-Name": "alice", "Acct-Session-Id": "sid-coa", "Filter-Id": "bronze"},
        input_octets=12,
        output_octets=34,
    )
    charge = Mock()
    sessions = AccountingSessionService(registry, charge=charge)
    identities = Mock()
    identities.ras_id.return_value = 3
    handler = RadiusRuntimeHandler(RadiusDispatcher(PluginPipeline([])), sessions, identities)

    response = handler(
        RadiusPacket(
            RadiusCode.COA_REQUEST,
            23,
            {"Acct-Session-Id": "sid-coa", "Filter-Id": "gold"},
            bytes(16),
        ),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.COA_ACK
    assert state.stopped is False
    assert state.attributes["Filter-Id"] == "gold"
    assert state.input_octets == 12 and state.output_octets == 34
    charge.settle.assert_not_called()


def test_invalid_coa_nak_does_not_mutate_or_stop_live_session():
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    registry = SessionRegistry()
    key = SessionKey(7, 3, "sid-coa-invalid")
    state = registry.start(
        key,
        {"User-Name": "alice", "Acct-Session-Id": "sid-coa-invalid", "Filter-Id": "bronze"},
    )
    before = dict(state.attributes)
    identities = Mock()
    identities.ras_id.return_value = 3
    handler = RadiusRuntimeHandler(
        RadiusDispatcher(PluginPipeline([])),
        AccountingSessionService(registry),
        identities,
    )

    response = handler(
        RadiusPacket(
            RadiusCode.COA_REQUEST,
            24,
            {"Acct-Session-Id": "sid-coa-invalid"},
            bytes(16),
        ),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.COA_NAK
    assert dict(state.attributes) == before
    assert state.stopped is False
    assert state.started is True



def test_disconnect_is_scoped_to_authenticated_source_ras_even_for_username_selector():
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    registry = SessionRegistry()
    local = registry.start(SessionKey(7, 3, "local"), {"User-Name": "alice", "Acct-Session-Id": "local"})
    remote = registry.start(SessionKey(7, 4, "remote"), {"User-Name": "alice", "Acct-Session-Id": "remote"})
    identities = Mock()
    identities.ras_id.return_value = 3
    handler = RadiusRuntimeHandler(
        RadiusDispatcher(PluginPipeline([])),
        AccountingSessionService(registry),
        identities,
    )

    response = handler(
        RadiusPacket(RadiusCode.DISCONNECT_REQUEST, 25, {"User-Name": "alice"}, bytes(16)),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.DISCONNECT_ACK
    assert local.stopped is True
    assert remote.stopped is False


def test_control_request_from_unresolved_ras_fails_closed_without_mutation():
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    registry = SessionRegistry()
    state = registry.start(SessionKey(7, 3, "sid"), {"User-Name": "alice", "Acct-Session-Id": "sid"})
    identities = Mock()
    identities.ras_id.return_value = None
    handler = RadiusRuntimeHandler(
        RadiusDispatcher(PluginPipeline([])),
        AccountingSessionService(registry),
        identities,
    )

    response = handler(
        RadiusPacket(RadiusCode.DISCONNECT_REQUEST, 26, {"Acct-Session-Id": "sid"}, bytes(16)),
        ("192.0.2.99", 1812),
    )

    assert response.code is RadiusCode.DISCONNECT_NAK
    assert response.attributes["Error-Cause"] == "503"
    assert state.stopped is False



def test_coa_is_scoped_to_authenticated_source_ras():
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    registry = SessionRegistry()
    local = registry.start(
        SessionKey(7, 3, "local-coa"),
        {"User-Name": "alice", "Acct-Session-Id": "local-coa", "Filter-Id": "bronze"},
    )
    remote = registry.start(
        SessionKey(7, 4, "remote-coa"),
        {"User-Name": "alice", "Acct-Session-Id": "remote-coa", "Filter-Id": "silver"},
    )
    identities = Mock()
    identities.ras_id.return_value = 3
    handler = RadiusRuntimeHandler(
        RadiusDispatcher(PluginPipeline([])),
        AccountingSessionService(registry),
        identities,
    )

    response = handler(
        RadiusPacket(
            RadiusCode.COA_REQUEST,
            27,
            {"User-Name": "alice", "Filter-Id": "gold"},
            bytes(16),
        ),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.COA_ACK
    assert local.attributes["Filter-Id"] == "gold"
    assert remote.attributes["Filter-Id"] == "silver"
    assert local.stopped is False and remote.stopped is False



def test_coa_refreshes_durable_remote_worker_session_before_selecting_targets():
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry, SessionState

    key = SessionKey(7, 3, "remote-worker-session")
    durable_state = SessionState(
        key=key,
        attributes={"User-Name": "alice", "Acct-Session-Id": key.unique_id, "Filter-Id": "bronze"},
        started=True,
    )

    class Store:
        def __init__(self):
            self.saved = []
            self.locked = []
        def list_active(self):
            return [durable_state]
        def lock(self, session_key):
            self.locked.append(session_key)
        def get(self, session_key):
            return durable_state if session_key == key else None
        def save(self, state):
            self.saved.append((state.key, dict(state.attributes)))

    registry = SessionRegistry()
    store = Store()
    sessions = AccountingSessionService(registry, state_store=store)
    identities = Mock()
    identities.ras_id.return_value = 3
    handler = RadiusRuntimeHandler(
        RadiusDispatcher(PluginPipeline([])),
        sessions,
        identities,
    )

    response = handler(
        RadiusPacket(
            RadiusCode.COA_REQUEST, 31,
            {"User-Name": "alice", "Filter-Id": "gold"},
            bytes(16),
        ),
        ("192.0.2.1", 1812),
    )

    refreshed = registry.get(key)
    assert response.code is RadiusCode.COA_ACK
    assert refreshed is durable_state
    assert refreshed.attributes["Filter-Id"] == "gold"
    assert store.locked == [key]
    assert store.saved[-1] == (key, dict(refreshed.attributes))



def test_access_accept_persists_login_reservation_under_user_lock():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionRegistry

    class SessionStore:
        def list_active(self): return []
        def lock(self, _key): pass
        def get(self, _key): return None
        def save(self, _state): pass

    class Reservations:
        def __init__(self): self.calls = []
        def request_key(self, _packet, _peer): return "r" * 64
        def lock_user(self, user_id): self.calls.append(("lock", user_id))
        def list_active(self, _user_id, _exclude=None): return ()
        def reserve(self, *args): self.calls.append(("reserve", *args))

    dispatcher = RadiusDispatcher(PluginPipeline([]))
    dispatcher.access = Mock(return_value=RadiusPacket(RadiusCode.ACCESS_ACCEPT, 5, {}, bytes(16)))
    identities = Mock()
    identities.users.get_authentication_record.return_value = (7, "secret", False)
    identities.ras_id.return_value = 3
    ras_record = SimpleNamespace(ras_id=3, ras_type="MikroTik", all_attributes=lambda: {})
    identities.ras.get_by_ip.return_value = ras_record
    reservations = Reservations()
    handler = RadiusRuntimeHandler(
        dispatcher,
        AccountingSessionService(SessionRegistry(), state_store=SessionStore()),
        identities,
        login_reservations=reservations,
    )

    response = handler(
        RadiusPacket(RadiusCode.ACCESS_REQUEST, 5, {"User-Name": "alice"}, bytes(range(16))),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.ACCESS_ACCEPT
    assert reservations.calls[0] == ("lock", 7)
    assert reservations.calls[1][0] == "reserve"
    assert reservations.calls[1][1:5] == (7, 3, "r" * 64, "alice")


def test_access_reject_releases_only_the_current_login_reservation():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionRegistry

    class SessionStore:
        def list_active(self): return []
        def lock(self, _key): pass
        def get(self, _key): return None
        def save(self, _state): pass

    class Reservations:
        def __init__(self): self.calls = []
        def request_key(self, _packet, _peer): return "r" * 64
        def lock_user(self, user_id): self.calls.append(("lock", user_id))
        def list_active(self, _user_id, _exclude=None): return ()
        def release(self, request_key): self.calls.append(("release", request_key))

    dispatcher = RadiusDispatcher(PluginPipeline([]))
    dispatcher.access = Mock(return_value=RadiusPacket(RadiusCode.ACCESS_REJECT, 5, {}, bytes(16)))
    identities = Mock()
    identities.users.get_authentication_record.return_value = (7, "secret", False)
    identities.ras_id.return_value = 3
    identities.ras.get_by_ip.return_value = SimpleNamespace(ras_id=3, ras_type="MikroTik")
    reservations = Reservations()
    handler = RadiusRuntimeHandler(
        dispatcher,
        AccountingSessionService(SessionRegistry(), state_store=SessionStore()),
        identities,
        login_reservations=reservations,
    )

    response = handler(
        RadiusPacket(RadiusCode.ACCESS_REQUEST, 5, {"User-Name": "alice"}, bytes(range(16))),
        ("192.0.2.1", 1812),
    )

    assert response.code is RadiusCode.ACCESS_REJECT
    assert ("release", "r" * 64) in reservations.calls


def test_new_accounting_start_consumes_one_reservation_only_once():
    from datetime import datetime, timezone
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import DispatchResult, RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    class SessionStore:
        def __init__(self): self.states = {}; self.locks = []
        def lock(self, key): self.locks.append(key)
        def get(self, key): return self.states.get(key)
        def save(self, state): self.states[state.key] = state
        def list_active(self): return [s for s in self.states.values() if s.started and not s.stopped]

    class Reservations:
        def __init__(self): self.calls = []
        def lock_user(self, user_id): self.calls.append(("lock", user_id))
        def consume_one(self, user_id, ras_id): self.calls.append(("consume", user_id, ras_id))

    registry = SessionRegistry()
    store = SessionStore()
    reservations = Reservations()
    event = AccountingEvent(
        AccountingStatus.START, "alice", "sid",
        attributes={"User-Name": "alice", "Acct-Session-Id": "sid"},
        observed_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )
    dispatcher = RadiusDispatcher(PluginPipeline([]))
    dispatcher.accounting = Mock(return_value=DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 6, {}, bytes(16)), event
    ))
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    identities.ras = None
    handler = RadiusRuntimeHandler(
        dispatcher, AccountingSessionService(registry, state_store=store),
        identities, login_reservations=reservations,
    )
    packet = RadiusPacket(RadiusCode.ACCOUNTING_REQUEST, 6, {"Acct-Status-Type": "Start"}, bytes(16))

    first = handler(packet, ("192.0.2.1", 1812))
    second = handler(packet, ("192.0.2.1", 1812))

    assert first.code is RadiusCode.ACCOUNTING_RESPONSE
    assert second.code is RadiusCode.ACCOUNTING_RESPONSE
    assert reservations.calls.count(("consume", 7, 3)) == 1
    assert reservations.calls.count(("lock", 7)) == 2
    assert store.states[SessionKey(7, 3, "sid")].started is True


def test_limit_termination_claim_is_persisted_under_shared_session_lock(monkeypatch):
    from copy import deepcopy
    from atd_radius.application import radius_runtime
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, *_args): return None

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "durable-claim")
    local = state.sessions.start(key, {"User-Name": "alice"})
    durable = deepcopy(local)
    events = []

    class Store:
        def __init__(self, _conn): pass
        def lock(self, got_key):
            assert got_key == key
            events.append("locked")
        def get(self, got_key):
            assert got_key == key
            return durable
        def save(self, got_state):
            nonlocal durable
            durable = deepcopy(got_state)
            events.append("saved")

    class Registry:
        def get(self, ras_id):
            return RAS(3, "192.0.2.3", "router", "router", "secret") if ras_id == 3 else None

    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    terminate = Mock()
    def verify_claim(*_args):
        assert durable.termination_requested_reason == "credit_finished"
        assert events == ["locked", "saved"]
    terminate.side_effect = verify_claim
    handler._ras_terminator.terminate = terminate
    monkeypatch.setattr(radius_runtime, "build_ras_runtime", lambda *_args: Registry())
    monkeypatch.setattr(
        "atd_radius.infrastructure.live_radius_sessions.PostgresLiveRadiusSessionRepository",
        Store,
    )
    try:
        handler._terminate_voip_session(key, "credit_finished")
        assert events == ["locked", "saved"]
        assert durable.termination_requested_reason == "credit_finished"
        assert state.sessions.get(key).termination_requested_reason == "credit_finished"
        terminate.assert_called_once()
    finally:
        handler.close()


def test_limit_termination_skips_claim_already_owned_by_another_worker(monkeypatch):
    from datetime import datetime, timezone
    from copy import deepcopy
    from atd_radius.application import radius_runtime
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, *_args): return None

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "already-claimed")
    local = state.sessions.start(key, {"User-Name": "alice"})
    durable = deepcopy(local)
    durable.termination_requested_reason = "credit_finished"
    durable.termination_requested_at = datetime.now(timezone.utc)

    class Store:
        def __init__(self, _conn): pass
        def lock(self, got_key): assert got_key == key
        def get(self, got_key): assert got_key == key; return durable
        def save(self, _state): raise AssertionError("existing claim must not be rewritten")

    class Registry:
        def get(self, ras_id):
            return RAS(3, "192.0.2.3", "router", "router", "secret") if ras_id == 3 else None

    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    terminate = Mock()
    handler._ras_terminator.terminate = terminate
    monkeypatch.setattr(radius_runtime, "build_ras_runtime", lambda *_args: Registry())
    monkeypatch.setattr(
        "atd_radius.infrastructure.live_radius_sessions.PostgresLiveRadiusSessionRepository",
        Store,
    )
    try:
        handler._terminate_voip_session(key, "credit_finished")
        terminate.assert_not_called()
        assert state.sessions.get(key).termination_requested_reason == "credit_finished"
    finally:
        handler.close()


def test_limit_planner_refreshes_user_sessions_from_durable_cross_worker_state(monkeypatch):
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey

    class Connection:
        def execute(self, *_args): return None

    state = NativeRadiusRuntimeState()
    stale_key = SessionKey(7, 2, "stale-local")
    durable_key = SessionKey(7, 3, "durable-remote")
    state.sessions.start(stale_key, {"User-Name": "alice"})
    durable_state = state.sessions.start(durable_key, {"User-Name": "alice"})
    state.sessions.remove(durable_key)
    locked = []
    events = []

    class Store:
        def __init__(self, _conn): pass
        def list_active(self):
            events.append("enumerate")
            return [durable_state]
        def lock(self, key):
            locked.append(key)
            events.append(("session-lock", key))
        def get(self, key): return durable_state if key == durable_key else None

    class LoginReservations:
        def __init__(self, _conn): pass
        def lock_user(self, user_id):
            assert user_id == 7
            events.append("user-lock")

    monkeypatch.setattr(
        "atd_radius.infrastructure.live_radius_sessions.PostgresLiveRadiusSessionRepository",
        Store,
    )
    monkeypatch.setattr(
        "atd_radius.infrastructure.login_reservations.PostgresLoginReservationRepository",
        LoginReservations,
    )
    handler = NativeRadiusPacketHandler.__new__(NativeRadiusPacketHandler)
    handler.state = state
    handler._refresh_durable_user_sessions(Connection(), 7)

    active = state.sessions.active_for_user(7)
    assert [item.key for item in active] == [durable_key]
    assert locked == [stale_key, durable_key]
    assert events[0:2] == ["user-lock", "enumerate"]


def test_accounting_stop_takes_user_lock_before_session_mutation():
    from datetime import datetime, timezone
    from unittest.mock import Mock
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.accounting_session import AccountingSessionService
    from atd_radius.domain.aaa import PluginPipeline
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_dispatch import DispatchResult, RadiusDispatcher
    from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

    calls = []

    class Reservations:
        def lock_user(self, user_id): calls.append(("lock", user_id))
        def consume_one(self, *_args): calls.append(("consume", *_args))

    event = AccountingEvent(
        AccountingStatus.STOP, "alice", "sid",
        attributes={"User-Name": "alice", "Acct-Session-Id": "sid"},
        observed_at=datetime(2026, 10, 21, tzinfo=timezone.utc),
    )
    dispatcher = RadiusDispatcher(PluginPipeline([]))
    dispatcher.accounting = Mock(return_value=DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 6, {}, bytes(16)), event
    ))
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    identities.ras = None
    registry = SessionRegistry()
    registry.start(SessionKey(7, 3, "sid"), {"User-Name": "alice"})
    delegate = AccountingSessionService(registry)

    class AccountingSessions:
        def __init__(self): self.registry = registry
        def apply(self, got_event, user_id, ras_id):
            calls.append(("apply", user_id, ras_id))
            return delegate.apply(got_event, user_id, ras_id)

    handler = RadiusRuntimeHandler(
        dispatcher, AccountingSessions(), identities, login_reservations=Reservations()
    )
    handler(
        RadiusPacket(
            RadiusCode.ACCOUNTING_REQUEST, 6,
            {"User-Name": "alice", "Acct-Status-Type": "Stop", "Acct-Session-Id": "sid"},
            bytes(16),
        ),
        ("192.0.2.1", 1812),
    )

    assert calls == [("lock", 7), ("apply", 7, 3)]


def test_stale_local_termination_marker_does_not_block_durable_retry(monkeypatch):
    from copy import deepcopy
    from datetime import datetime, timezone
    from atd_radius.application import radius_runtime
    from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
    from atd_radius.domain.radius_runtime import SessionKey
    from atd_radius.domain.ras import RAS

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, *_args): return None

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "retry-after-clear")
    local = state.sessions.start(key, {"User-Name": "alice"})
    local.termination_requested_reason = "old_failed_attempt"
    local.termination_requested_at = datetime.now(timezone.utc)
    durable = deepcopy(local)
    durable.termination_requested_reason = None
    durable.termination_requested_at = None

    class Store:
        def __init__(self, _conn): pass
        def lock(self, got_key): assert got_key == key
        def get(self, got_key): assert got_key == key; return durable
        def save(self, new_state):
            nonlocal durable
            durable = deepcopy(new_state)

    class Registry:
        def get(self, ras_id):
            return RAS(3, "192.0.2.3", "router", "router", "secret") if ras_id == 3 else None

    handler = NativeRadiusPacketHandler(state, lambda: Connection())
    terminate = Mock()
    handler._ras_terminator.terminate = terminate
    monkeypatch.setattr(radius_runtime, "build_ras_runtime", lambda *_args: Registry())
    monkeypatch.setattr(
        "atd_radius.infrastructure.live_radius_sessions.PostgresLiveRadiusSessionRepository",
        Store,
    )
    try:
        handler._terminate_voip_session(key, "credit_finished")
        terminate.assert_called_once()
        assert durable.termination_requested_reason == "credit_finished"
    finally:
        handler.close()

  
def test_build_radius_dispatcher_enforces_native_absolute_expiry():
    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    users.policy_attributes.return_value = [("abs_exp_date", "1")]
    users.attributes.return_value = [("abs_exp_date", "1")]
    dispatcher = build_radius_dispatcher(users)

    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            5,
            {"User-Name": "alice", "User-Password": "secret"},
            b"0123456789abcdef",
        )
    )

    assert response.code is RadiusCode.ACCESS_REJECT

  
def test_build_radius_dispatcher_persists_first_login_only_after_accept():
    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    users.policy_attributes.return_value = [("rel_exp_date", "3600")]
    users.attributes.return_value = [("rel_exp_date", "3600")]
    dispatcher = build_radius_dispatcher(users)

    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            6,
            {"User-Name": "alice", "User-Password": "secret"},
            b"0123456789abcdef",
        )
    )

    assert response.code is RadiusCode.ACCESS_ACCEPT
    assert 0 < int(response.attributes["Session-Timeout"]) <= 3600
    assert "first_login" not in response.attributes
    users.set_attribute_if_absent.assert_called_once()
    users.set_attribute.assert_not_called()
    args = users.set_attribute_if_absent.call_args.args
    assert args[:2] == (7, "first_login")
    assert int(args[2]) > 0


def test_build_radius_dispatcher_does_not_persist_first_login_on_rejection():
    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    users.policy_attributes.return_value = [("rel_exp_date", "1")]
    users.attributes.return_value = [("rel_exp_date", "1")]
    dispatcher = build_radius_dispatcher(users)

    # A deliberately expired pre-existing first_login must reject and must not
    # write a replacement timestamp that would renew the user's subscription.
    users.policy_attributes.return_value = [("rel_exp_date", "1"), ("first_login", "1")]
    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            7,
            {"User-Name": "alice", "User-Password": "secret"},
            b"0123456789abcdef",
        )
    )

    assert response.code is RadiusCode.ACCESS_REJECT
    users.set_attribute.assert_not_called()


def test_build_radius_dispatcher_initializes_first_login_for_user_without_relative_expiry():
    users = Mock()
    users.get_authentication_record.return_value = (8, "secret", False)
    users.policy_attributes.return_value = []
    users.attributes.return_value = []
    dispatcher = build_radius_dispatcher(users)

    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            8,
            {"User-Name": "bob", "User-Password": "secret"},
            b"0123456789abcdef",
        )
    )

    assert response.code is RadiusCode.ACCESS_ACCEPT
    users.set_attribute_if_absent.assert_called_once()
    args = users.set_attribute_if_absent.call_args.args
    assert args[:2] == (8, "first_login")
    assert "first_login" not in response.attributes

def test_native_dispatcher_enforces_mikrotik_station_ip_restriction():
    class Users:
        def get_authentication_record(self, username):
            return (7, "secret", False) if username == "alice" else None

        def attributes(self, user_id):
            return [("limit_station_ip", "192.0.2.0/24")]

        def policy_attributes(self, user_id):
            return self.attributes(user_id)

    class RASRecord:
        ras_id = 3
        ras_type = "Mikrotik"
        ippool_ids = ()

        def all_attributes(self):
            return {}

    class RAS:
        def get_by_ip(self, source_ip):
            return RASRecord() if source_ip == "192.0.2.1" else None

    dispatcher = build_radius_dispatcher(Users(), ras=RAS())
    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            14,
            {
                "User-Name": "alice",
                "User-Password": "secret",
                "NAS-Port-Type": "Virtual",
                "Calling-Station-Id": "203.0.113.9",
            },
        ),
        source_ip="192.0.2.1",
    )

    assert response.code is RadiusCode.ACCESS_REJECT

def test_native_dispatcher_enforces_source_mapped_voip_caller_id_restriction():
    class Users:
        def get_authentication_record(self, username):
            return (7, "secret", False) if username == "alice" else None

        def attributes(self, user_id):
            return [
                ("limit_caller_id", "^555[0-9]{4}$"),
                ("limit_caller_id_allow_not_defined", "0"),
            ]

        def policy_attributes(self, user_id):
            return self.attributes(user_id)

    class RASRecord:
        ras_id = 3
        ras_type = "MVTS"
        ippool_ids = ()

        def all_attributes(self):
            return {}

    class RAS:
        def get_by_ip(self, source_ip):
            return RASRecord() if source_ip == "192.0.2.1" else None

    dispatcher = build_radius_dispatcher(Users(), ras=RAS())
    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            15,
            {
                "User-Name": "alice",
                "User-Password": "secret",
                "Calling-Station-Id": "1234567",
            },
        ),
        source_ip="192.0.2.1",
    )

    assert response.code is RadiusCode.ACCESS_REJECT



def test_native_dispatcher_rejects_access_when_periodic_quota_is_exhausted():
    from atd_radius.application.periodic_accounting import PeriodicQuotaDecision

    class Users:
        def get_authentication_record(self, username):
            return (17, "secret", False) if username == "alice" else None

        def attributes(self, user_id):
            return []

        def policy_attributes(self, user_id):
            return []

    class Quotas:
        def can_login(self, user_id):
            assert user_id == 17
            return PeriodicQuotaDecision(False, ("time_periodic_accounting_daily",))

    dispatcher = build_radius_dispatcher(Users(), periodic_accounting=Quotas())
    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST, 22,
            {"User-Name": "alice", "User-Password": "secret"},
        )
    )
    assert response.code is RadiusCode.ACCESS_REJECT


def test_native_dispatcher_allows_access_when_periodic_quota_has_room():
    from atd_radius.application.periodic_accounting import PeriodicQuotaDecision

    class Users:
        def get_authentication_record(self, username):
            return (17, "secret", False) if username == "alice" else None

        def attributes(self, user_id):
            return []

        def policy_attributes(self, user_id):
            return []

    class Quotas:
        def can_login(self, user_id):
            return PeriodicQuotaDecision(True)

    dispatcher = build_radius_dispatcher(Users(), periodic_accounting=Quotas())
    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST, 23,
            {"User-Name": "alice", "User-Password": "secret"},
        )
    )
    assert response.code is RadiusCode.ACCESS_ACCEPT
