import math
import pytest

from atd_radius.domain.periodic_accounting import (
    PeriodicAccountingState,
    PeriodicQuotaConfig,
    PeriodicQuotaKind,
    a124_next_month_reset,
    _gregorian_to_jalali,
)


def config(kind=PeriodicQuotaKind.TIME, **overrides):
    values = dict(key="time_periodic_accounting_daily", period="daily",
                  kind=kind, value="1", limit=3600, next_reset=200000,
                  accumulated_usage=0)
    values.update(overrides)
    return PeriodicQuotaConfig(**values)


def test_time_quota_includes_committed_initial_and_all_active_instance_usage():
    state = PeriodicAccountingState(config(), initial_usage=30, committed_usage=40)
    state.starts = {1: 1000.0, 2: 1100.0}
    assert state.current_usage(1200) == 30 + 40 + 200 + 100
    snapshot = state.snapshot(1200)
    assert snapshot.usage == 370
    assert snapshot.remaining == 3230
    assert not snapshot.quota_finished


def test_traffic_quota_uses_input_plus_output_baseline_delta_and_clamps_counter_reset():
    state = PeriodicAccountingState(config(
        kind=PeriodicQuotaKind.TRAFFIC, limit=1000), initial_usage=100)
    state.starts = {1: 500, 2: 800}
    assert state.current_usage(0, {1: 650, 2: 700}) == 250
    assert state.logout(1, 0, traffic_octets=650) == 150
    assert state.current_usage(0, {2: 700}) == 250


def test_login_captures_baseline_before_quota_decision():
    state = PeriodicAccountingState(config(limit=100, accumulated_usage=100))
    assert state.login(1, now=1234)
    assert state.starts[1] == 1234


def test_logout_commits_instance_once():
    state = PeriodicAccountingState(config(), initial_usage=5)
    state.login(1, 100)
    assert state.logout(1, 145) == 45
    assert state.logout(1, 160) == 0
    assert state.current_usage(160) == 50


def test_daily_reset_advances_from_saved_epoch_by_whole_intervals():
    state = PeriodicAccountingState(config(next_reset=1000), initial_usage=500)
    assert state.refresh_reset_if_due(1001)
    assert state.next_reset == 1000 + 86400
    assert state.current_usage(1001) == 0
    assert not state.refresh_reset_if_due(2000)


def test_reset_rebases_active_instances_instead_of_losing_post_reset_usage():
    state = PeriodicAccountingState(config(next_reset=1000))
    state.starts = {1: 900.0}
    assert state.refresh_reset_if_due(1001)
    assert state.starts == {1: 1001}
    assert state.current_usage(1015) == 14


def test_monthly_reset_uses_injected_source_calendar_result_without_guessing():
    state = PeriodicAccountingState(config(period="monthly", value="jalali", next_reset=1000))
    assert state.refresh_reset_if_due(1000, lambda calendar: 4000)
    assert state.next_reset == 4000


def test_a124_gregorian_and_jalali_month_helpers_return_local_midnight():
    import time
    for calendar in ("gregorian", "jalali"):
        next_reset = a124_next_month_reset(calendar, now=1_793_000_000)
        local = time.localtime(next_reset)
        assert next_reset > 1_793_000_000
        if calendar == "gregorian":
            assert local.tm_mday == 1
        else:
            assert _gregorian_to_jalali(local.tm_year, local.tm_mon, local.tm_mday)[2] == 1
        assert (local.tm_hour, local.tm_min, local.tm_sec) == (0, 0, 0)


def test_traffic_remaining_time_matches_per_instance_assumed_kps_formula():
    state = PeriodicAccountingState(config(
        kind=PeriodicQuotaKind.TRAFFIC, limit=102400, accumulated_usage=0))
    assert state.remaining_time(0, instances=2, counters={}, assumed_kps={1: 10, 2: 20}) == pytest.approx(7.5)
    assert math.isinf(state.remaining_time(0, instances=2, normal_user=False))


@pytest.mark.parametrize("period,value", [("daily", "0"), ("daily", "-1"), ("monthly", "other")])
def test_invalid_periodic_accounting_configuration_fails_closed(period, value):
    with pytest.raises(ValueError):
        PeriodicQuotaConfig("key", period, PeriodicQuotaKind.TIME, value, 100)
