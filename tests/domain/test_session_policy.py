from atd_radius.domain.models import AttributeSet
from atd_radius.domain.session_policy import ActiveSessionView, session_policy


def test_multilogin_allows_up_to_source_limit():
    attrs = AttributeSet({"multi_login": "1"})
    assert session_policy(attrs, [ActiveSessionView("s1")]).allowed


def test_multilogin_rejects_only_above_source_limit():
    attrs = AttributeSet({"multi_login": "1"})
    decision = session_policy(attrs, [ActiveSessionView("s1"), ActiveSessionView("s2")])
    assert not decision.allowed
    assert decision.reason == "multi_login"


def test_multilogin_zero_allows_first_login():
    attrs = AttributeSet({"multi_login": "0"})
    assert session_policy(attrs, []).allowed
