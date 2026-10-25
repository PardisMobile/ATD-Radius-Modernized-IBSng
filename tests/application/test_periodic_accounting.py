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
