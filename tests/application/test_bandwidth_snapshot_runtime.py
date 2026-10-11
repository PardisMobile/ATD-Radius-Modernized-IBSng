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


def test_runtime_records_bandwidth_deltas_only_for_normal_users_with_save_marker():
    start_at = datetime(2026, 10, 12, 12, 0, 10, tzinfo=timezone.utc)
    interim_at = datetime(2026, 10, 12, 12, 0, 25, tzinfo=timezone.utc)
    events = [
        AccountingEvent(AccountingStatus.START, "alice", "sid", input_octets=100,
                        output_octets=200, observed_at=start_at),
        AccountingEvent(AccountingStatus.INTERIM, "alice", "sid", input_octets=150,
                        output_octets=260, observed_at=interim_at),
    ]
    dispatcher = Mock()
    dispatcher.accounting.side_effect = [
        DispatchResult(RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 9, {}, b"0123456789abcdef"), event)
        for event in events
    ]
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    identities.ras.get.return_value = None
    identities.users.normal_credentials.return_value = ("alice", "stored-hash")
    identities.users.policy_attributes.return_value = [("save_bw_usage", "")]
    snapshot_repo = Mock()
    service = AccountingSessionService(SessionRegistry())
    handler = RadiusRuntimeHandler(
        dispatcher, service, identities, bandwidth_snapshots=snapshot_repo
    )

    handler(packet(), ("192.0.2.1", 1812))
    handler(packet(), ("192.0.2.1", 1812))

    snapshot_repo.record_usage.assert_called_once_with(interim_at, 7, 50, 60)


def test_runtime_does_not_record_bandwidth_when_marker_is_absent_or_user_is_not_normal():
    event = AccountingEvent(
        AccountingStatus.INTERIM, "alice", "sid", input_octets=10,
        output_octets=20, observed_at=datetime(2026, 10, 12, 12, 1, tzinfo=timezone.utc)
    )
    dispatcher = Mock()
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 9, {}, b"0123456789abcdef"), event
    )
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3
    identities.ras.get.return_value = None
    identities.users.normal_credentials.return_value = ("alice", "stored-hash")
    identities.users.policy_attributes.return_value = [("comment", "ordinary")]
    snapshot_repo = Mock()
    handler = RadiusRuntimeHandler(
        dispatcher, AccountingSessionService(SessionRegistry()), identities,
        bandwidth_snapshots=snapshot_repo
    )

    handler(packet(), ("192.0.2.1", 1812))

    snapshot_repo.record_usage.assert_not_called()

    identities.users.normal_credentials.return_value = None
    identities.users.policy_attributes.return_value = [("save_bw_usage", "")]
    handler(packet(), ("192.0.2.1", 1812))
    snapshot_repo.record_usage.assert_not_called()
