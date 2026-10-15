from threading import Event
from time import monotonic

import pytest

from atd_radius.application.voip_limit_scheduler import VoipLimitScheduler


def test_scheduler_runs_callback_and_reschedules_until_callback_returns_none():
    scheduler = VoipLimitScheduler()
    fired = Event()
    calls = []

    def callback():
        calls.append(monotonic())
        if len(calls) == 2:
            fired.set()
            return None
        return 1

    scheduler.schedule("user:7", 1, callback)
    scheduler.start()
    try:
        assert fired.wait(3)
        assert len(calls) == 2
        assert "user:7" not in scheduler.pending_keys()
    finally:
        scheduler.close()


def test_cancel_invalidates_pending_callback():
    scheduler = VoipLimitScheduler()
    fired = Event()
    scheduler.schedule("session:abc", 1, lambda: fired.set())
    assert scheduler.cancel("session:abc")
    scheduler.start()
    try:
        assert not fired.wait(1.2)
        assert scheduler.pending_keys() == ()
    finally:
        scheduler.close()


def test_replacing_key_does_not_allow_old_callback_to_reschedule():
    scheduler = VoipLimitScheduler()
    entered = Event()
    release = Event()
    replacement = Event()

    def old_callback():
        entered.set()
        assert release.wait(2)
        return 1

    scheduler.schedule("user:9", 1, old_callback)
    scheduler.start()
    try:
        assert entered.wait(2)
        scheduler.schedule("user:9", 1, lambda: (replacement.set(), None)[1])
        release.set()
        assert replacement.wait(3)
    finally:
        release.set()
        scheduler.close()


def test_callback_error_is_reported_and_not_silently_rescheduled():
    fired = Event()
    errors = []

    def report(key, exc):
        errors.append((key, exc))
        fired.set()

    def fail():
        raise RuntimeError("database transaction failed")

    scheduler = VoipLimitScheduler(on_error=report)
    scheduler.schedule("user:11", 1, fail)
    scheduler.start()
    try:
        assert fired.wait(2)
        assert errors[0][0] == "user:11"
        assert isinstance(errors[0][1], RuntimeError)
        assert scheduler.pending_keys() == ()
    finally:
        scheduler.close()


@pytest.mark.parametrize("delay", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_scheduler_rejects_non_positive_or_non_finite_delays(delay):
    scheduler = VoipLimitScheduler()
    with pytest.raises(ValueError):
        scheduler.schedule("user:1", delay, lambda: None)
    scheduler.close()
