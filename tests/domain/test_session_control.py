from atd_radius.domain.radius_runtime import SessionKey,SessionRegistry
from atd_radius.domain.session_control import RegistrySessionControl

def test_disconnect_stops_matching_session():
    r=SessionRegistry(); k=SessionKey(1,2,"sid"); r.start(k,{"User-Name":"u"})
    assert RegistrySessionControl(r).disconnect({"Acct-Session-Id":"sid"})
    assert r.get(k).stopped

def test_coa_updates_live_session_attributes():
    r=SessionRegistry(); k=SessionKey(1,2,"sid"); r.start(k,{"Session-Timeout":"100"})
    assert RegistrySessionControl(r).change_of_authorization({"Acct-Session-Id":"sid","Session-Timeout":"50"})
    assert r.get(k).attributes["Session-Timeout"]=="50"
