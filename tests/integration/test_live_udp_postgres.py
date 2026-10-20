

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
