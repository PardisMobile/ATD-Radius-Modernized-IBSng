from datetime import datetime, timedelta, timezone

import pytest

from atd_radius.domain.accounting import (
    AccountingError,
    AccountingPolicy,
    UsageSnapshot,
    should_record_usage,
    usage_delta,
)


def test_save_bw_usage_controls_recording():
    assert should_record_usage(AccountingPolicy(save_bw_usage=True)) is True
    assert should_record_usage(AccountingPolicy(save_bw_usage=False)) is False


def test_usage_delta_handles_normal_and_reset_counters():
    start = datetime.now(timezone.utc)
    previous = UsageSnapshot("u", "s", start, input_octets=100, output_octets=200)
    current = UsageSnapshot("u", "s", start, input_octets=150, output_octets=260)
    assert usage_delta(previous, current) == (50, 60)
    reset = UsageSnapshot("u", "s", start, input_octets=10, output_octets=20)
    assert usage_delta(previous, reset) == (0, 0)


def test_usage_duration_rejects_negative_time():
    now = datetime.now(timezone.utc)
    snapshot = UsageSnapshot("u", "s", now, ended_at=now - timedelta(seconds=1))
    with pytest.raises(AccountingError):
        _ = snapshot.duration_seconds
