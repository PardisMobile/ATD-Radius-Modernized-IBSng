from datetime import datetime, timezone

from atd_radius.domain.models import AttributeSet
from atd_radius.domain.session_policy import (
    ActiveSessionView,
    SessionAdmissionReason,
    session_deadline,
    session_policy,
)


def test_locked_user_is_rejected():
    decision = session_policy(AttributeSet({"lock": True}))
    assert decision.allowed is False
    assert decision.reason == SessionAdmissionReason.LOCKED


def test_multi_login_numeric_limit():
    active = [ActiveSessionView("one")]
    allowed = session_policy(AttributeSet({"multi_login": 2}), active)
    denied = session_policy(AttributeSet({"multi_login": 1}), active)
    assert allowed.allowed is True
    assert denied.allowed is False
    assert denied.reason == SessionAdmissionReason.MULTI_LOGIN


def test_timeouts_are_exposed_and_deadline_is_deterministic():
    decision = session_policy(AttributeSet({"session_timeout": "3600", "idle_timeout": 300}))
    assert decision.session_timeout_seconds == 3600
    assert decision.idle_timeout_seconds == 300
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert session_deadline(started, decision.session_timeout_seconds).isoformat() == "2026-01-01T01:00:00+00:00"
