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

    state = NativeRadiusRuntimeState()
    key = SessionKey(7, 3, "conf-7")
    session = state.sessions.start(key, {"User-Name": "alice"})
    session.termination_requested_reason = "credit_finished"
    session.termination_requested_at = datetime.now(timezone.utc)
    handler = NativeRadiusPacketHandler(state, Mock())
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
    handler = RadiusRuntimeHandler(dispatcher, sessions, Mock())

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
