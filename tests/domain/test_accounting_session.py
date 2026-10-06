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
