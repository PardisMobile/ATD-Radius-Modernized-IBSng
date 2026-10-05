from datetime import datetime,timezone
from atd_radius.domain.aaa import AAAAction,AAARequest,AAAResult,PluginPipeline
from atd_radius.domain.user_policies import LockPolicy,MultiLoginPolicy,TimeoutPolicy,AbsoluteExpiryPolicy
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
