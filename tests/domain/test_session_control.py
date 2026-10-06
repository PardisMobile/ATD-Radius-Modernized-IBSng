from atd_radius.domain.radius_runtime import SessionKey,SessionRegistry
from atd_radius.domain.session_control import RegistrySessionControl

def test_disconnect_stops_matching_session():
    r=SessionRegistry(); k=SessionKey(1,2,"sid"); r.start(k,{"User-Name":"u","Acct-Session-Id":"sid"})
    result=RegistrySessionControl(r).disconnect({"Acct-Session-Id":"sid"})
    assert result.ok and result.error_cause is None
    assert r.get(k).stopped

def test_coa_updates_supported_authorization_on_live_session():
    r=SessionRegistry(); k=SessionKey(1,2,"sid"); r.start(k,{"User-Name":"u","Acct-Session-Id":"sid"})
    result=RegistrySessionControl(r).change_of_authorization({"Acct-Session-Id":"sid","Filter-Id":"gold"})
    assert result.ok
    assert r.get(k).attributes["Filter-Id"]=="gold"

def test_matching_applies_to_all_sessions():
    r=SessionRegistry()
    r.start(SessionKey(1,2,"sid-1"),{"User-Name":"u","NAS-Identifier":"nas-1","Acct-Session-Id":"sid-1"})
    r.start(SessionKey(1,2,"sid-2"),{"User-Name":"u","NAS-Identifier":"nas-1","Acct-Session-Id":"sid-2"})
    result=RegistrySessionControl(r).disconnect({"User-Name":"u","NAS-Identifier":"nas-1"})
    assert result.ok
    assert r.get(SessionKey(1, 2, "sid-1")).stopped\n    assert r.get(SessionKey(1, 2, "sid-2")).stopped

def test_unknown_session_returns_503():
    r=SessionRegistry()
    result=RegistrySessionControl(r).disconnect({"Acct-Session-Id":"missing"})
    assert not result.ok and result.error_cause=="503"

def test_unsupported_disconnect_attribute_returns_401():
    r=SessionRegistry()
    r.start(SessionKey(1,2,"sid"),{"User-Name":"u","Acct-Session-Id":"sid"})
    result=RegistrySessionControl(r).disconnect({"Acct-Session-Id":"sid","Filter-Id":"not-allowed"})
    assert not result.ok and result.error_cause=="401"

def test_missing_session_identifier_returns_402():
    r=SessionRegistry()
    result=RegistrySessionControl(r).disconnect({"NAS-Identifier":"nas-1"})
    assert not result.ok and result.error_cause=="402"
