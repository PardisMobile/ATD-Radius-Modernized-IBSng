from datetime import datetime
from unittest.mock import Mock

from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
from atd_radius.infrastructure.accounting_persistence import NativeAccountingPersistence


def test_start_maps_accounting_event_to_native_connection_log():
    repository = Mock()
    repository.create.return_value = 42
    clock = lambda: datetime(2026, 10, 6, 10, 0)
    persistence = NativeAccountingPersistence(repository, clock)

    event = AccountingEvent(
        AccountingStatus.START,
        "alice",
        "sid-1",
        remote_ip="10.0.0.5",
        attributes={"NAS-Port": "7"},
    )

    assert persistence.start(event, 11, 3) == 42
    record = repository.create.call_args.args[0]
    assert record.user_id == 11
    assert record.ras_id == 3
    assert record.service == 1
    assert record.login_time == clock()
    assert record.details["Acct-Session-Id"] == "sid-1"
    assert record.details["Framed-IP-Address"] == "10.0.0.5"
    assert record.details["NAS-Port"] == "7"


def test_stop_updates_details_without_duplicate_insert():
    repository = Mock()
    persistence = NativeAccountingPersistence(repository, lambda: datetime(2026, 10, 6, 11, 0))
    event = AccountingEvent(
        AccountingStatus.STOP,
        "alice",
        "sid-1",
        input_octets=100,
        output_octets=200,
        attributes={"NAS-Port": "8"},
    )

    persistence.stop(42, event)

    assert repository.upsert_detail.call_count == 2
    repository.close.assert_called_once_with(42, datetime(2026, 10, 6, 11, 0), None, True)



def test_voip_start_persists_authoritative_ras_connect_time():
    repository = Mock()
    clock = lambda: datetime(2026, 10, 6, 10, 0)
    persistence = NativeAccountingPersistence(repository, clock)
    connect_time = datetime(2026, 10, 5, 22, 15, 30).timestamp()
    event = AccountingEvent(
        AccountingStatus.START,
        "voip-alice",
        "voip-sid",
        attributes={"connect_time": str(connect_time)},
    )

    persistence.start(event, 11, 3)

    record = repository.create.call_args.args[0]
    assert record.login_time == datetime(2026, 10, 5, 22, 15, 30)
    assert record.login_time != clock()


def test_voip_stop_persists_ras_disconnect_time_without_credit_policy():
    repository = Mock()
    clock = lambda: datetime(2026, 10, 6, 11, 0)
    persistence = NativeAccountingPersistence(repository, clock)
    disconnect_time = datetime(2026, 10, 5, 22, 18, 30).timestamp()
    event = AccountingEvent(
        AccountingStatus.STOP,
        "voip-alice",
        "voip-sid",
        attributes={"disconnect_time": str(disconnect_time)},
    )

    persistence.stop(42, event, credit_used=None)

    repository.close.assert_called_once_with(
        42, datetime(2026, 10, 5, 22, 18, 30), None, True
    )


def test_invalid_ras_epoch_time_falls_back_to_existing_accounting_clock():
    repository = Mock()
    clock_value = datetime(2026, 10, 6, 10, 0)
    persistence = NativeAccountingPersistence(repository, lambda: clock_value)
    event = AccountingEvent(
        AccountingStatus.START,
        "alice",
        "sid-invalid-ras-time",
        attributes={"connect_time": "not-an-epoch"},
    )

    persistence.start(event, 11, 3)

    assert repository.create.call_args.args[0].login_time == clock_value
