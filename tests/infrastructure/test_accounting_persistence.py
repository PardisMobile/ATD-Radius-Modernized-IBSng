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
