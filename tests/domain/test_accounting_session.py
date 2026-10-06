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
    persistence.stop.assert_called_once()
    assert persistence.stop.call_args.args[0] == 99
    assert persistence.stop.call_args.args[1].session_id == "sid-p"


def test_duplicate_start_does_not_create_a_second_connection_log():
    from unittest.mock import Mock
    persistence = Mock()
    persistence.start.return_value = 123
    service = AccountingSessionService(SessionRegistry(), persistence)
    first = service.apply(event(AccountingStatus.START, "dup", 100, 200), 7, 3)
    second = service.apply(event(AccountingStatus.START, "dup", 999, 999), 7, 3)
    assert first.connection_log_id == second.connection_log_id == 123
    assert second.state.input_octets == 100
    persistence.start.assert_called_once()


def test_duplicate_stop_does_not_update_persistence_twice_or_resurrect_session():
    from unittest.mock import Mock
    persistence = Mock()
    persistence.start.return_value = 124
    service = AccountingSessionService(SessionRegistry(), persistence)
    service.apply(event(AccountingStatus.START, "stop-dup", 100, 200), 7, 3)
    first = service.apply(event(AccountingStatus.STOP, "stop-dup", 150, 260), 7, 3)
    second = service.apply(event(AccountingStatus.STOP, "stop-dup", 999, 999), 7, 3)
    assert first.state.stopped and second.state.stopped
    assert (second.delta_input_octets, second.delta_output_octets) == (0, 0)
    persistence.stop.assert_called_once()


def test_interim_after_stop_does_not_resurrect_session():
    service = AccountingSessionService(SessionRegistry())
    service.apply(event(AccountingStatus.START, "after-stop", 10, 20), 7, 3)
    service.apply(event(AccountingStatus.STOP, "after-stop", 20, 30), 7, 3)
    result = service.apply(event(AccountingStatus.INTERIM, "after-stop", 50, 60), 7, 3)
    assert result.state.stopped
    assert result.state.input_octets == 20
    assert result.state.output_octets == 30


def test_alive_is_a1_24_accounting_update_and_persists_delta():
    from unittest.mock import Mock
    persistence = Mock()
    persistence.start.return_value = 125
    service = AccountingSessionService(SessionRegistry(), persistence)
    service.apply(event(AccountingStatus.START, "alive", 100, 200), 7, 3)
    result = service.apply(event(AccountingStatus.ALIVE, "alive", 140, 260), 7, 3)
    assert (result.delta_input_octets, result.delta_output_octets) == (40, 60)
    persistence.update.assert_called_once()


def test_alive_after_stop_does_not_resurrect_session():
    service = AccountingSessionService(SessionRegistry())
    service.apply(event(AccountingStatus.START, "alive-stop", 10, 20), 7, 3)
    service.apply(event(AccountingStatus.STOP, "alive-stop", 20, 30), 7, 3)
    result = service.apply(event(AccountingStatus.ALIVE, "alive-stop", 50, 60), 7, 3)
    assert result.state.stopped
    assert result.state.input_octets == 20
    assert result.state.output_octets == 30


def test_no_connection_log_suppresses_native_persistence():
    from unittest.mock import Mock
    persistence = Mock()
    persistence.start.return_value = 42
    service = AccountingSessionService(SessionRegistry(), persistence)
    result = service.apply(event(AccountingStatus.START, "nolog", attributes={"no_connection_log": "1"}), 7, 3)
    assert result.connection_log_id is None
    persistence.start.assert_not_called()
