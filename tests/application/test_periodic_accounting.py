import pytest

from atd_radius.application.periodic_accounting import PeriodicAccountingCoordinator


class MemoryAttributes:
    def __init__(self, initial):
        self.values = dict(initial)
        self.saved = []

    def load(self, user_id):
        return dict(self.values)

    def save(self, user_id, values):
        self.values.update(values)
        self.saved.append((user_id, dict(values)))


def attrs(**overrides):
    result = {
        "time_periodic_accounting_daily": "1",
        "time_periodic_accounting_daily_limit": "100",
        "time_periodic_accounting_daily_usage": "0",
        "time_periodic_accounting_daily_reset": "200000",
    }
    result.update(overrides)
    return result


def test_coordinator_login_logout_persists_accumulated_usage():
    clock = [1000.0]
    repo = MemoryAttributes(attrs())
    coordinator = PeriodicAccountingCoordinator(repo, clock=lambda: clock[0])
    decision = coordinator.login(7, 1, start_accounting=True)
    assert decision.allowed
    clock[0] = 1030.5
    assert coordinator.logout(7, 1)["time_periodic_accounting_daily"] == 30.5
    assert repo.values["time_periodic_accounting_daily_usage"] == "30.5"


def test_coordinator_denies_and_requests_termination_when_quota_exhausted():
    clock = [1000.0]
    repo = MemoryAttributes(attrs(time_periodic_accounting_daily_usage="100"))
    killed = []
    coordinator = PeriodicAccountingCoordinator(
        repo, clock=lambda: clock[0],
        request_termination=lambda user, key: killed.append((user, key)),
    )
    result = coordinator.login(7, 1)
    assert not result.allowed
    assert result.exhausted_keys == ("time_periodic_accounting_daily",)
    assert killed == []  # login rejection is handled by the caller, not a live-session kill


def test_can_stay_online_requests_termination_for_exhausted_active_quota():
    clock = [1000.0]
    repo = MemoryAttributes(attrs(time_periodic_accounting_daily_usage="100"))
    killed = []
    coordinator = PeriodicAccountingCoordinator(
        repo, clock=lambda: clock[0],
        request_termination=lambda user, key: killed.append((user, key)),
    )
    coordinator.login(7, 1)
    result = coordinator.can_stay_online(7, 1)
    assert not result.allowed
    assert killed == [(7, "time_periodic_accounting_daily")]


def test_traffic_coordinator_tracks_active_instance_counter_delta():
    clock = [1000.0]
    repo = MemoryAttributes({
        "traffic_periodic_accounting_daily": "1",
        "traffic_periodic_accounting_daily_limit": "1000",
        "traffic_periodic_accounting_daily_usage": "0",
        "traffic_periodic_accounting_daily_reset": "200000",
    })
    counts = {1: 100, 2: 400}
    coordinator = PeriodicAccountingCoordinator(
        repo, clock=lambda: clock[0],
        traffic_counters=lambda user, instance: counts[instance],
    )
    assert coordinator.login(7, 1, start_accounting=True).allowed
    counts[1] = 250
    assert coordinator.update(7, 1).allowed
    assert coordinator.logout(7, 1)["traffic_periodic_accounting_daily"] == 150
    assert repo.values["traffic_periodic_accounting_daily_usage"] == "150"


def test_login_without_start_accounting_does_not_charge_session_usage():
    clock = [1000.0]
    repo = MemoryAttributes(attrs())
    coordinator = PeriodicAccountingCoordinator(repo, clock=lambda: clock[0])
    assert coordinator.login(7, 1).allowed
    clock[0] = 1200.0
    assert coordinator.logout(7, 1)["time_periodic_accounting_daily"] == 0


def test_coordinator_accepts_composite_native_session_identity():
    clock = [1000.0]
    repo = MemoryAttributes(attrs())
    coordinator = PeriodicAccountingCoordinator(repo, clock=lambda: clock[0])
    assert coordinator.login(7, "12:session-A", start_accounting=True).allowed
    clock[0] = 1042.0
    assert coordinator.logout(7, "12:session-A")["time_periodic_accounting_daily"] == 42
    assert repo.values["time_periodic_accounting_daily_usage"] == "42.0"


def test_can_login_rejects_exhausted_quota_without_creating_instance():
    repo = MemoryAttributes(attrs(time_periodic_accounting_daily_usage="100"))
    coordinator = PeriodicAccountingCoordinator(repo, clock=lambda: 1000.0)
    decision = coordinator.can_login(7)
    assert not decision.allowed
    assert decision.exhausted_keys == ("time_periodic_accounting_daily",)
    assert coordinator._users[7].quotas["time_periodic_accounting_daily"].starts == {}


def test_reload_changed_period_value_resets_usage_and_rebases_active_instances():
    clock = [1000.0]
    initial = attrs()
    repo = MemoryAttributes(initial)
    coordinator = PeriodicAccountingCoordinator(repo, clock=lambda: clock[0])
    coordinator.login(7, "1:session", start_accounting=True)
    state = coordinator._users[7].quotas["time_periodic_accounting_daily"]
    state.committed_usage = 55
    repo.values["time_periodic_accounting_daily"] = "2"
    repo.values.pop("time_periodic_accounting_daily_usage", None)
    repo.values.pop("time_periodic_accounting_daily_reset", None)
    clock[0] = 1100.0
    coordinator.reload_user(7)
    state = coordinator._users[7].quotas["time_periodic_accounting_daily"]
    assert state.committed_usage == 0
    assert state.initial_usage == 0
    assert state.starts["1:session"] == 1100.0
    assert state.next_reset is not None and state.next_reset > 1100.0


def test_reload_unchanged_period_refreshes_persisted_usage_without_losing_baseline():
    clock = [1000.0]
    repo = MemoryAttributes(attrs())
    coordinator = PeriodicAccountingCoordinator(repo, clock=lambda: clock[0])
    coordinator.login(7, "1:session", start_accounting=True)
    state = coordinator._users[7].quotas["time_periodic_accounting_daily"]
    repo.values["time_periodic_accounting_daily_usage"] = "25"
    coordinator.reload_user(7)
    state = coordinator._users[7].quotas["time_periodic_accounting_daily"]
    assert state.committed_usage == 25
    assert state.starts["1:session"] == 1000.0


def test_session_baselines_restore_across_coordinator_restart():
    clock = [1000.0]
    repo = MemoryAttributes(attrs())
    first = PeriodicAccountingCoordinator(repo, clock=lambda: clock[0])
    first.login(7, "12:session-A", start_accounting=True)
    markers = first.session_baseline_attributes(7, "12:session-A")
    assert markers["__periodic_start_time_periodic_accounting_daily"] == "1000.0"
    assert markers["__periodic_value_time_periodic_accounting_daily"] == "1"

    clock[0] = 1030.0
    second = PeriodicAccountingCoordinator(repo, clock=lambda: clock[0])
    second.restore_instance(7, "12:session-A", markers)
    state = second._users[7].quotas["time_periodic_accounting_daily"]
    assert state.current_usage(1030.0) == 30.0


def test_restart_rebases_session_when_period_value_changed():
    clock = [1000.0]
    repo = MemoryAttributes(attrs(time_periodic_accounting_daily="2"))
    coordinator = PeriodicAccountingCoordinator(repo, clock=lambda: clock[0])
    coordinator.restore_instance(
        7, "12:session-A",
        {
            "__periodic_start_time_periodic_accounting_daily": "500.0",
            "__periodic_value_time_periodic_accounting_daily": "1",
        },
    )
    state = coordinator._users[7].quotas["time_periodic_accounting_daily"]
    assert state.starts["12:session-A"] == 1000.0


def test_coordinator_uses_effective_assumed_kps_for_traffic_quota_deadline():
    clock = [1000.0]
    repo = MemoryAttributes({
        "traffic_periodic_accounting_daily": "1",
        "traffic_periodic_accounting_daily_limit": "3000",
        "traffic_periodic_accounting_daily_usage": "0",
        "traffic_periodic_accounting_daily_reset": "200000",
    })
    counts = {"1:a": 0, "2:b": 0}
    coordinator = PeriodicAccountingCoordinator(
        repo,
        clock=lambda: clock[0],
        traffic_counters=lambda user, instance: counts[instance],
        assumed_kps=lambda user, instance: 10,
    )
    coordinator.login(7, "1:a", start_accounting=True)
    coordinator.login(7, "2:b", start_accounting=True)
    result = coordinator.can_stay_online(7, "1:a")
    assert result.remaining_seconds == pytest.approx(3000 / 2 / (10 * 1024) * 2)


def test_traffic_periodic_quota_does_not_apply_to_voip_users():
    clock = [1000.0]
    repo = MemoryAttributes({
        "traffic_periodic_accounting_daily": "1",
        "traffic_periodic_accounting_daily_limit": "10",
        "traffic_periodic_accounting_daily_usage": "999",
        "traffic_periodic_accounting_daily_reset": "200000",
    })
    counts = {"1:voip": 5000}
    coordinator = PeriodicAccountingCoordinator(
        repo,
        clock=lambda: clock[0],
        traffic_counters=lambda user, instance: counts[instance],
        is_normal_user=lambda user: False,
    )
    assert coordinator.can_login(7).allowed
    assert coordinator.login(7, "1:voip", start_accounting=True).allowed
    clock[0] = 2000.0
    assert coordinator.logout(7, "1:voip")["traffic_periodic_accounting_daily"] == 0
    assert repo.values["traffic_periodic_accounting_daily_usage"] == "999"



def test_concurrent_first_access_loads_user_state_once():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    from time import sleep

    class CountingAttributes(MemoryAttributes):
        def __init__(self, initial):
            super().__init__(initial)
            self.load_count = 0
            self.load_lock = Lock()

        def load(self, user_id):
            with self.load_lock:
                self.load_count += 1
            # Widen the race window: without per-user synchronization, several
            # callers can all observe an empty cache and overwrite its state.
            sleep(0.01)
            return super().load(user_id)

    repo = CountingAttributes(attrs())
    coordinator = PeriodicAccountingCoordinator(repo, clock=lambda: 1000.0)
    start = Barrier(12)

    def access():
        start.wait()
        return coordinator.has_quotas(7)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: access(), range(12)))

    assert all(results)
    assert repo.load_count == 1
    assert set(coordinator._users[7].quotas) == {"time_periodic_accounting_daily"}
