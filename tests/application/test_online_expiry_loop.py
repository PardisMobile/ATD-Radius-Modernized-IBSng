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
