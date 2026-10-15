from threading import Event

import pytest

from atd_radius.application.voip_limit_loop import VoipLimitCheckLoop
from atd_radius.application.voip_limit_scheduler import VoipLimitScheduler
from atd_radius.domain.accounting_charge import VoipLimitPlan
from atd_radius.domain.radius_runtime import SessionKey


def test_limit_loop_executes_per_session_kill_reason_and_stops_without_next_event():
    checked = Event()
    calls = []
    kills = []

    def check(user_id):
        calls.append(user_id)
        checked.set()
        return VoipLimitPlan(0, (("call-42", "credit_finished"),))

    loop = VoipLimitCheckLoop(VoipLimitScheduler(), check, lambda session, reason: kills.append((session, reason)))
    loop.schedule(7)
    loop.start()
    try:
        assert checked.wait(2)
        # Wait until callback's kill action has completed before inspecting it.
        import time
        deadline = time.monotonic() + 1
        while not kills and time.monotonic() < deadline:
            time.sleep(0.01)
        assert calls == [7]
        assert kills == [(SessionKey(7, 3, "call-42"), "credit_finished")]
    finally:
        loop.close()


def test_limit_loop_rechecks_after_next_boundary():
    finished = Event()
    calls = []
    plans = iter((VoipLimitPlan(1), VoipLimitPlan(None)))

    def check(user_id):
        calls.append(user_id)
        if len(calls) == 2:
            finished.set()
        return next(plans)

    loop = VoipLimitCheckLoop(VoipLimitScheduler(), check, lambda _session, _reason: None)
    loop.schedule(8)
    loop.start()
    try:
        assert finished.wait(3)
        assert calls == [8, 8]
    finally:
        loop.close()


def test_limit_loop_retries_provider_kill_failure_after_rechecking_plan():
    second_attempt = Event()
    attempts = []
    checks = []

    def check(user_id):
        checks.append(user_id)
        return VoipLimitPlan(0, (("call-99", "no_effective_rule"),))

    def terminate(session, reason):
        attempts.append((session, reason))
        if len(attempts) == 1:
            raise OSError("provider temporarily unavailable")
        second_attempt.set()

    loop = VoipLimitCheckLoop(VoipLimitScheduler(), check, terminate)
    loop.schedule(9)
    loop.start()
    try:
        assert second_attempt.wait(4)
        assert attempts == [
            (SessionKey(9, 3, "call-99"), "no_effective_rule"),
            (SessionKey(9, 3, "call-99"), "no_effective_rule"),
        ]
        assert len(checks) >= 2
    finally:
        loop.close()


def test_limit_loop_rejects_invalid_user_id():
    loop = VoipLimitCheckLoop(VoipLimitScheduler(), lambda _user: VoipLimitPlan(None), lambda _s, _r: None)
    with pytest.raises(ValueError):
        loop.schedule(0)
    loop.close()
