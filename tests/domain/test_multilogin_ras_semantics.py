from unittest.mock import Mock

from atd_radius.domain.aaa import AAAAction, AAARequest
from atd_radius.domain.user_policies import MultiLoginPolicy, ras_allows_multi_login
from atd_radius.domain.session_policy import ActiveSessionView


def test_ras_multilogin_source_defaults():
    assert ras_allows_multi_login("BSAE", {}) is False
    assert ras_allows_multi_login("Mikrotik", {}) is True
    assert ras_allows_multi_login("Cisco", {}) is True


def test_voip_ras_multilogin_attributes_match_a124():
    assert ras_allows_multi_login("GnuGk", {}) is False
    assert ras_allows_multi_login("GnuGk", {"gnugk_multiple_login": "1"}) is True
    assert ras_allows_multi_login("Asterisk", {}) is False
    assert ras_allows_multi_login("Asterisk", {"asterisk_multi_login": "1"}) is True
    assert ras_allows_multi_login("Quintum Tenor", {}) is False


def test_ras_does_not_override_user_limit_precedence():
    policy = MultiLoginPolicy(active_sessions=(ActiveSessionView("s1"),))
    request = AAARequest("alice", {
        "multi_login": "1",
        "__ras_multi_login_allowed": "0",
    })
    result = policy.evaluate(request)
    assert result is not None
    assert result.action is AAAAction.REJECT
    assert result.reason == "MAX_CONCURRENT"


def test_ras_does_not_allow_second_session_when_user_limit_allows_it():
    policy = MultiLoginPolicy(active_sessions=(ActiveSessionView("s1"),))
    request = AAARequest("alice", {
        "multi_login": "2",
        "__ras_multi_login_allowed": "0",
    })
    result = policy.evaluate(request)
    assert result is not None
    assert result.action is AAAAction.REJECT
    assert result.reason == "RAS_DOESNT_ALLOW_MULTILOGIN"
