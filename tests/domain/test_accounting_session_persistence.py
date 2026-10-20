from datetime import datetime, timezone
from decimal import Decimal

from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
from atd_radius.domain.accounting_session import AccountingSessionService
from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry


class Persistence:
    def __init__(self):
        self.discarded = []
        self.stopped = []
    def start(self, event, user_id, ras_id):
        return 100
    def update(self, log_id, event):
        pass
    def stop(self, log_id, event, credit_used=None):
        self.stopped.append((log_id, credit_used))
    def discard(self, log_id):
        self.discarded.append(log_id)


class Charge:
    def start(self, *_args):
        pass
    def update(self, *_args):
        pass
    def settle(self, *_args):
        return Decimal("1.25")


class StateStore:
    def __init__(self):
        self.saved = []
        self.deleted = []
    def save(self, state):
        if state.started and not state.stopped:
            self.saved.append((state.key, dict(state.attributes)))
        else:
            self.deleted.append(state.key)


def event(status, *, attrs=None, when=None, in_octets=0, out_octets=0):
    return AccountingEvent(
        status=status, username="alice", session_id="sid",
        input_octets=in_octets, output_octets=out_octets,
        attributes=attrs or {}, observed_at=when or datetime(2026, 10, 20, tzinfo=timezone.utc),
    )


def test_accounting_start_and_interim_persist_full_live_state_snapshot():
    registry = SessionRegistry()
    store = StateStore()
    service = AccountingSessionService(registry, Persistence(), Charge(), store)
    service.apply(event(AccountingStatus.START, in_octets=10, out_octets=20), 7, 3)
    service.apply(event(AccountingStatus.INTERIM, in_octets=30, out_octets=40), 7, 3)
    assert len(store.saved) == 2
    assert store.saved[-1][1]["__connection_log_id"] == "100"
    assert registry.get(SessionKey(7, 3, "sid")).input_octets == 30


def test_stop_removes_live_snapshot_and_no_connection_log_discards_opened_history():
    registry = SessionRegistry()
    store = StateStore()
    persistence = Persistence()
    service = AccountingSessionService(registry, persistence, Charge(), store)
    service.apply(event(AccountingStatus.START), 7, 3)
    result = service.apply(event(AccountingStatus.STOP, attrs={"no_connection_log": "1"}), 7, 3)
    assert result.state.stopped is True
    assert persistence.discarded == [100]
    assert persistence.stopped == []
    assert store.deleted == [SessionKey(7, 3, "sid")]
