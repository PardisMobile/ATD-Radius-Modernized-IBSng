from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
from atd_radius.domain.accounting_session import AccountingSessionService
from atd_radius.domain.radius_runtime import SessionRegistry

def event(status, sid="s", inp=0, out=0):
    return AccountingEvent(status, "alice", sid, input_octets=inp, output_octets=out)

def test_accounting_session_start_interim_stop_tracks_deltas():
    service = AccountingSessionService(SessionRegistry())
    started = service.apply(event(AccountingStatus.START, inp=100, out=200), 7, 3)
    assert started.state.started and not started.state.stopped

    interim = service.apply(event(AccountingStatus.INTERIM, inp=150, out=260), 7, 3)
    assert (interim.delta_input_octets, interim.delta_output_octets) == (50, 60)

    stopped = service.apply(event(AccountingStatus.STOP, inp=180, out=300), 7, 3)
    assert (stopped.delta_input_octets, stopped.delta_output_octets) == (30, 40)
    assert stopped.state.stopped

def test_interim_without_start_creates_session():
    service = AccountingSessionService(SessionRegistry())
    result = service.apply(event(AccountingStatus.INTERIM, inp=10, out=20), 7, 3)
    assert result.state.started and not result.state.stopped

def test_stop_without_session_is_rejected():
    service = AccountingSessionService(SessionRegistry())
    try:
        service.apply(event(AccountingStatus.STOP), 7, 3)
    except LookupError:
        return
    assert False, "expected LookupError"


def test_accounting_session_persists_start_and_stop_using_connection_log_id():
    from unittest.mock import Mock

    persistence = Mock()
    persistence.start.return_value = 99
    service = AccountingSessionService(SessionRegistry(), persistence)
    started = service.apply(event(AccountingStatus.START, "sid-p", 100, 200), 7, 3)
    assert started.connection_log_id == 99
    assert started.state.attributes["__connection_log_id"] == "99"
    stopped = service.apply(event(AccountingStatus.STOP, "sid-p", 150, 260), 7, 3)
    assert stopped.connection_log_id == 99
    persistence.start.assert_called_once()
    persistence.stop.assert_called_once_with(99, stopped_event := stopped and event(AccountingStatus.STOP, "sid-p", 150, 260))
