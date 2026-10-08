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

def test_relative_expiry_sets_first_login_on_first_login():
    now=datetime.fromtimestamp(1000,tz=timezone.utc)
    r=RelativeExpiryPolicy(now).evaluate(AAARequest("u",{"rel_exp_date":"3600"}))
    assert r.attributes["first_login"]=="1000"

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
