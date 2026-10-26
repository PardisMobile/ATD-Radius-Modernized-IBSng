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


def test_traffic_quota_uses_raw_a124_baseline_deltas_even_if_counter_decreases():
    state = PeriodicAccountingState(config(
        kind=PeriodicQuotaKind.TRAFFIC, limit=1000), initial_usage=100)
    state.starts = {1: 500, 2: 800}
    assert state.current_usage(0, {1: 650, 2: 700}) == 150
    assert state.logout(1, 0, traffic_octets=650) == 150
    assert state.current_usage(0, {2: 700}) == 150


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


def test_login_quota_check_includes_existing_active_instance_counters():
    state = PeriodicAccountingState(config(kind=PeriodicQuotaKind.TRAFFIC, limit=1000))
    state.starts = {1: 100}
    assert state.login(2, now=1000, traffic_octets=100, counters={1: 1100})


def test_time_usage_keeps_fractional_seconds_until_persistence_boundary():
    state = PeriodicAccountingState(config(limit=100))
    state.starts = {1: 10.25}
    assert state.current_usage(10.75) == 0.5
    assert state.logout(1, 10.75) == 0.5


def test_native_session_string_is_valid_for_periodic_baselines():
    state = PeriodicAccountingState(config())
    assert not state.login("42:session-A", now=1000)
    assert state.starts["42:session-A"] == 1000
    assert state.logout("42:session-A", now=1030) == 30


def test_traffic_quota_deadline_uses_composite_runtime_session_keys():
    state = PeriodicAccountingState(config(kind=PeriodicQuotaKind.TRAFFIC, limit=3000))
    state.starts = {"1:session-A": 100, "2:session-B": 200}
    result = state.remaining_time(
        0,
        instances=2,
        counters={"1:session-A": 100, "2:session-B": 200},
        assumed_kps={"1:session-A": 10, "2:session-B": 10},
    )
    assert result == pytest.approx(3000 / 2 / (10 * 1024) * 2)


def test_reset_is_not_repeated_at_the_exact_reset_boundary():
    state = PeriodicAccountingState(PeriodicQuotaConfig(
        key="time_periodic_accounting_daily",
        period="daily",
        kind=PeriodicQuotaKind.TIME,
        value="1",
        limit=100,
        next_reset=2000.0,
        accumulated_usage=25,
    ))
    assert not state.refresh_reset_if_due(2000.0)
    assert state.committed_usage == 25
    assert state.next_reset == 2000.0

    assert state.refresh_reset_if_due(2000.001)
    assert state.committed_usage == 0
    assert state.next_reset > 2000.001
