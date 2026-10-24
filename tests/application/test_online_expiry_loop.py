from atd_radius.application.online_expiry_loop import plan_online_expiry
from atd_radius.domain.radius_runtime import SessionKey

def test_absolute_expiry_terminates_every_active_session():
    sessions = (SessionKey(7, 3, "port-1"), SessionKey(7, 4, "port-2"))
    plan = plan_online_expiry({"abs_exp_date": "99"}, sessions, now=100)
    assert plan.remaining_seconds == 0
    assert plan.kill_reasons == ((sessions[0], "absolute_expired"), (sessions[1], "absolute_expired"))

def test_relative_expiry_uses_persisted_first_login_and_earliest_deadline():
    session = SessionKey(7, 3, "sid")
    plan = plan_online_expiry({"abs_exp_date": "250", "rel_exp_date": "100", "first_login": "100"}, (session,), now=210)
    assert plan.remaining_seconds == 0
    assert plan.kill_reasons == ((session, "relative_expired"),)

def test_future_expiry_returns_remaining_seconds_without_killing():
    session = SessionKey(7, 3, "sid")
    plan = plan_online_expiry({"abs_exp_date": "250"}, (session,), now=200)
    assert plan.remaining_seconds == 50
    assert plan.kill_reasons == ()

def test_no_expiry_or_no_active_sessions_does_not_schedule_termination():
    session = SessionKey(7, 3, "sid")
    assert plan_online_expiry({}, (session,), now=200).remaining_seconds is None
    assert plan_online_expiry({"abs_exp_date": "1"}, (), now=200).kill_reasons == ()


def test_expiry_loop_terminates_all_sessions_from_an_expired_plan():
    from threading import Event
    from atd_radius.application.online_expiry_loop import OnlineSessionExpiryLoop, OnlineExpiryPlan
    from atd_radius.application.voip_limit_scheduler import VoipLimitScheduler

    finished = Event()
    first = SessionKey(7, 3, "port-1")
    second = SessionKey(7, 4, "port-2")
    calls = []

    def terminate(key, reason):
        calls.append((key, reason))
        if len(calls) == 2:
            finished.set()

    loop = OnlineSessionExpiryLoop(
        VoipLimitScheduler(name="test-online-expiry"),
        lambda _user_id: OnlineExpiryPlan(0, ((first, "absolute_expired"), (second, "absolute_expired"))),
        terminate,
    )
    loop.schedule(7)
    loop.start()
    try:
        assert finished.wait(2)
        assert calls == [
            (first, "absolute_expired"),
            (second, "absolute_expired"),
        ]
    finally:
        loop.close()


def test_expiry_loop_retries_transient_termination_failure():
    from threading import Event
    from atd_radius.application.online_expiry_loop import OnlineSessionExpiryLoop, OnlineExpiryPlan
    from atd_radius.application.voip_limit_scheduler import VoipLimitScheduler

    retried = Event()
    key = SessionKey(7, 3, "port-9")
    attempts = []

    def terminate(session_key, reason):
        attempts.append((session_key, reason))
        if len(attempts) == 1:
            raise OSError("temporary RAS outage")
        retried.set()

    loop = OnlineSessionExpiryLoop(
        VoipLimitScheduler(name="test-online-expiry-retry"),
        lambda _user_id: OnlineExpiryPlan(0, ((key, "relative_expired"),)),
        terminate,
    )
    loop.schedule(7)
    loop.start()
    try:
        assert retried.wait(4)
        assert attempts == [(key, "relative_expired"), (key, "relative_expired")]
    finally:
        loop.close()
