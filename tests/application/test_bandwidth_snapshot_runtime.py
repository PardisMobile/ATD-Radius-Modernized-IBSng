from datetime import datetime, timezone
from unittest.mock import Mock

from atd_radius.application.radius_runtime import RadiusRuntimeHandler
from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
from atd_radius.domain.accounting_session import AccountingSessionService
from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_dispatch import DispatchResult
from atd_radius.domain.radius_runtime import SessionRegistry


def packet():
    return RadiusPacket(
        RadiusCode.ACCOUNTING_REQUEST, 9, {"Acct-Status-Type": "Interim-Update"},
        b"0123456789abcdef"
    )


def event(status, input_octets, output_octets, observed_at):
    return AccountingEvent(
        status, "alice", "sid", input_octets=input_octets,
        output_octets=output_octets, observed_at=observed_at,
    )


def setup_handler(events, *, normal=True, marker=True):
    dispatcher = Mock()
    dispatcher.accounting.side_effect = [
        DispatchResult(
            RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 9, {}, b"0123456789abcdef"),
            item,
        )
        for item in events
    ]
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    identities.ras.get.return_value = None
    identities.users.normal_credentials.return_value = ("alice", "stored-hash") if normal else None
    identities.users.policy_attributes.return_value = [("save_bw_usage", "")] if marker else []
    snapshots = Mock()
    handler = RadiusRuntimeHandler(
        dispatcher, AccountingSessionService(SessionRegistry()), identities,
        bandwidth_snapshots=snapshots,
    )
    return handler, snapshots


def test_runtime_records_bandwidth_deltas_only_for_normal_users_with_save_marker():
    start_at = datetime(2026, 10, 12, 12, 0, 10, tzinfo=timezone.utc)
    interim_at = datetime(2026, 10, 12, 12, 0, 25, tzinfo=timezone.utc)
    handler, snapshot_repo = setup_handler([
        event(AccountingStatus.START, 100, 200, start_at),
        event(AccountingStatus.INTERIM, 150, 260, interim_at),
    ])

    handler(packet(), ("192.0.2.1", 1812))
    handler(packet(), ("192.0.2.1", 1812))

    snapshot_repo.record_usage.assert_called_once_with(interim_at, 7, 50, 60)


def test_runtime_skips_bandwidth_snapshot_without_effective_save_marker():
    start_at = datetime(2026, 10, 12, 12, 1, 0, tzinfo=timezone.utc)
    interim_at = datetime(2026, 10, 12, 12, 1, 15, tzinfo=timezone.utc)
    handler, snapshot_repo = setup_handler([
        event(AccountingStatus.START, 100, 200, start_at),
        event(AccountingStatus.INTERIM, 150, 260, interim_at),
    ], marker=False)

    handler(packet(), ("192.0.2.1", 1812))
    handler(packet(), ("192.0.2.1", 1812))

    snapshot_repo.record_usage.assert_not_called()


def test_runtime_skips_bandwidth_snapshot_for_non_normal_user():
    start_at = datetime(2026, 10, 12, 12, 2, 0, tzinfo=timezone.utc)
    interim_at = datetime(2026, 10, 12, 12, 2, 15, tzinfo=timezone.utc)
    handler, snapshot_repo = setup_handler([
        event(AccountingStatus.START, 100, 200, start_at),
        event(AccountingStatus.INTERIM, 150, 260, interim_at),
    ], normal=False, marker=True)

    handler(packet(), ("192.0.2.1", 1812))
    handler(packet(), ("192.0.2.1", 1812))

    snapshot_repo.record_usage.assert_not_called()


def test_runtime_records_final_stop_counter_delta_for_snapshot_enabled_user():
    start_at = datetime(2026, 10, 12, 12, 3, 0, tzinfo=timezone.utc)
    stop_at = datetime(2026, 10, 12, 12, 3, 30, tzinfo=timezone.utc)
    handler, snapshot_repo = setup_handler([
        event(AccountingStatus.START, 500, 900, start_at),
        event(AccountingStatus.STOP, 640, 1_000, stop_at),
    ])

    handler(packet(), ("192.0.2.1", 1812))
    handler(packet(), ("192.0.2.1", 1812))

    snapshot_repo.record_usage.assert_called_once_with(stop_at, 7, 140, 100)


def test_runtime_counter_reset_never_persists_negative_or_wrapped_bandwidth():
    start_at = datetime(2026, 10, 12, 12, 4, 0, tzinfo=timezone.utc)
    reset_at = datetime(2026, 10, 12, 12, 4, 15, tzinfo=timezone.utc)
    next_at = datetime(2026, 10, 12, 12, 4, 30, tzinfo=timezone.utc)
    handler, snapshot_repo = setup_handler([
        event(AccountingStatus.START, 500, 900, start_at),
        event(AccountingStatus.INTERIM, 10, 20, reset_at),
        event(AccountingStatus.INTERIM, 20, 30, next_at),
    ])

    for _ in range(3):
        handler(packet(), ("192.0.2.1", 1812))

    snapshot_repo.record_usage.assert_called_once_with(next_at, 7, 10, 10)
