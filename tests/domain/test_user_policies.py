from datetime import datetime,timezone
from atd_radius.domain.aaa import AAAAction,AAARequest,AAAResult,PluginPipeline
from atd_radius.domain.user_policies import LockPolicy,MultiLoginPolicy,TimeoutPolicy,AbsoluteExpiryPolicy,RelativeExpiryPolicy
from atd_radius.domain.session_policy import ActiveSessionView

class Marker:
    def __init__(self,key): self.key=key
    def evaluate(self,request): return AAAResult(AAAAction.ACCEPT,{self.key:"1"})

def test_all_accepting_plugins_run_in_order():
    r=PluginPipeline([Marker("a"),Marker("b")]).evaluate(AAARequest("u"))
    assert r.attributes=={"a":"1","b":"1"}

def test_lock_stops_later_plugins():
    r=PluginPipeline([LockPolicy(),Marker("never")]).evaluate(AAARequest("u",{"lock":"maintenance"}))
    assert r.action is AAAAction.REJECT and "never" not in r.attributes

def test_timeout_is_mapped_to_reply_attributes():
    r=TimeoutPolicy().evaluate(AAARequest("u",{"session_timeout":"600","idle_timeout":"30"}))
    assert r.attributes=={"Session-Timeout":"600","Idle-Timeout":"30"}

def test_multilogin_matches_a124_limit():
    p=MultiLoginPolicy((ActiveSessionView("s1"),))
    assert p.evaluate(AAARequest("u",{"multi_login":"1"})).reason=="MAX_CONCURRENT"

def test_absolute_expiry_rejects_expired_user():
    now=datetime.fromtimestamp(1000,tz=timezone.utc)
    r=AbsoluteExpiryPolicy(now).evaluate(AAARequest("u",{"abs_exp_date":"999"}))
    assert r.action is AAAAction.REJECT

def test_relative_expiry_uses_private_first_login_candidate_without_emitting_it():
    now=datetime.fromtimestamp(1000,tz=timezone.utc)
    r=RelativeExpiryPolicy(now).evaluate(
        AAARequest("u", {"rel_exp_date":"3600", "__first_login_candidate":"1000"})
    )
    assert r.attributes == {"Session-Timeout": "3600"}
    assert "first_login" not in r.attributes

def test_relative_expiry_rejects_after_deadline():
    now=datetime.fromtimestamp(5000,tz=timezone.utc)
    r=RelativeExpiryPolicy(now).evaluate(AAARequest("u",{"rel_exp_date":"3600","first_login":"1000"}))
    assert r.action is AAAAction.REJECT


def test_multilogin_live_provider_uses_active_sessions_for_user():
    sessions = {7: (ActiveSessionView("s1"),)}
    p = MultiLoginPolicy(active_sessions_provider=lambda user_id: sessions[user_id])
    request = AAARequest("u", {"__user_id": "7", "multi_login": "2"})
    assert p.evaluate(request) is None


def test_multilogin_live_provider_rejects_second_session_when_ras_disallows():
    sessions = {7: (ActiveSessionView("s1"),)}
    p = MultiLoginPolicy(active_sessions_provider=lambda user_id: sessions[user_id])
    request = AAARequest("u", {"__user_id": "7", "multi_login": "2", "ras_multi_login": "false"})
    assert p.evaluate(request).reason == "RAS_DOESNT_ALLOW_MULTILOGIN"


def test_multilogin_checks_limit_before_incoming_ras_capability():
    sessions = {7: (ActiveSessionView("s1", ras_multi_login_allowed=False),)}
    policy = MultiLoginPolicy(active_sessions_provider=lambda user_id: sessions[user_id])
    request = AAARequest("u", {
        "__user_id": "7", "multi_login": "1", "ras_multi_login": "false"
    })
    assert policy.evaluate(request).reason == "MAX_CONCURRENT"


def test_multilogin_normalizes_false_ras_capability_strings():
    sessions = {7: (ActiveSessionView("s1", ras_multi_login_allowed=True),)}
    policy = MultiLoginPolicy(active_sessions_provider=lambda user_id: sessions[user_id])
    for value in ("false", "FALSE", " false ", "0", False):
        request = AAARequest("u", {
            "__user_id": "7", "multi_login": "2", "__ras_multi_login_allowed": value
        })
        assert policy.evaluate(request).reason == "RAS_DOESNT_ALLOW_MULTILOGIN"


def test_multilogin_accepts_when_every_ras_allows_multiple_sessions():
    sessions = {7: (ActiveSessionView("s1", ras_multi_login_allowed=True),)}
    policy = MultiLoginPolicy(active_sessions_provider=lambda user_id: sessions[user_id])
    request = AAARequest("u", {
        "__user_id": "7", "multi_login": "2", "__ras_multi_login_allowed": True
    })
    assert policy.evaluate(request) is None

  
def test_timeout_policy_does_not_extend_absolute_expiry_deadline():
    from atd_radius.domain.user_policies import TimeoutPolicy

    result = TimeoutPolicy().evaluate(
        AAARequest("alice", {"session_timeout": "3600", "Session-Timeout": "45"})
    )

    assert result.attributes["Session-Timeout"] == "45"

  
def test_relative_expiry_does_not_extend_existing_shorter_session_timeout():
    now = datetime.fromtimestamp(1000, tz=timezone.utc)
    result = RelativeExpiryPolicy(now).evaluate(
        AAARequest(
            "u",
            {
                "rel_exp_date": "7200",
                "first_login": "1000",
                "Session-Timeout": "30",
            },
        )
    )

    assert result.attributes["Session-Timeout"] == "30"

def test_limit_mac_policy_matches_source_conditional_presence_semantics():
    from atd_radius.domain.user_policies import LimitMacPolicy

    policy = LimitMacPolicy()
    # A1.24 only checks when the RAS message contains mac.
    assert policy.evaluate(AAARequest("u", {"limit_mac": "AA,BB"})) is None
    assert policy.evaluate(AAARequest("u", {"limit_mac": "AA,BB", "mac": "BB"})) is None
    denied = policy.evaluate(AAARequest("u", {"limit_mac": "AA,BB", "mac": "CC"}))
    assert denied.action is AAAAction.REJECT
    assert denied.reason == "LOGIN_FROM_THIS_MAC_DENIED"


def test_limit_station_ip_policy_matches_single_addresses_and_cidr_ranges():
    from atd_radius.domain.user_policies import LimitStationIPPolicy

    policy = LimitStationIPPolicy()
    assert policy.evaluate(
        AAARequest("u", {"limit_station_ip": "192.0.2.7,198.51.100.0/24", "station_ip": "192.0.2.7"})
    ) is None
    assert policy.evaluate(
        AAARequest("u", {"limit_station_ip": "192.0.2.7,198.51.100.0/24", "station_ip": "198.51.100.22"})
    ) is None
    denied = policy.evaluate(
        AAARequest("u", {"limit_station_ip": "192.0.2.7,198.51.100.0/24", "station_ip": "203.0.113.8"})
    )
    assert denied.action is AAAAction.REJECT
    assert denied.reason == "LOGIN_FROM_THIS_IP_DENIED"


def test_limit_station_ip_policy_fails_closed_on_invalid_ip_or_stored_range():
    from atd_radius.domain.user_policies import LimitStationIPPolicy

    policy = LimitStationIPPolicy()
    for attrs in (
        {"limit_station_ip": "192.0.2.0/24", "station_ip": "not-an-ip"},
        {"limit_station_ip": "invalid-network", "station_ip": "192.0.2.7"},
    ):
        result = policy.evaluate(AAARequest("u", attrs))
        assert result.action is AAAAction.REJECT
        assert result.reason == "LOGIN_FROM_THIS_IP_DENIED"

def test_limit_mac_and_station_ip_empty_configured_attributes_do_not_disable_checks():
    from atd_radius.domain.user_policies import LimitMacPolicy, LimitStationIPPolicy

    mac = LimitMacPolicy().evaluate(AAARequest("u", {"limit_mac": "", "mac": "AA:BB"}))
    assert mac.action is AAAAction.REJECT
    assert mac.reason == "LOGIN_FROM_THIS_MAC_DENIED"

    station = LimitStationIPPolicy().evaluate(
        AAARequest("u", {"limit_station_ip": "", "station_ip": "192.0.2.1"})
    )
    assert station.action is AAAAction.REJECT
    assert station.reason == "LOGIN_FROM_THIS_IP_DENIED"

