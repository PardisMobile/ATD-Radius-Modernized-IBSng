from atd_radius.domain.ras_provider import (
    normalize_ras_type,
    provider_ip_assignment,
    provider_multi_login,
    provider_profile,
    provider_supports_status,
    provider_unique_id,
    provider_session_id,
)


def test_source_provider_identity_profiles():
    assert provider_unique_id("Mikrotik") == "port"
    assert provider_unique_id("BSAE") == "port"
    assert provider_unique_id("ChilliSpot") == "port"
    assert provider_unique_id("Cisco") == "port"
    assert provider_unique_id("Cisco VPDN") == "acct_session_id"
    assert provider_unique_id("PortMaster") == "port"
    assert provider_unique_id("PortSlave") == "port"
    assert provider_unique_id("Total Control") == "interface_index"
    assert provider_unique_id("Quintum Tenor") == "h323_conf_id"
    assert provider_unique_id("MVTS") == "h323_conf_id"
    assert provider_unique_id("SER") == "call_id"
    assert provider_unique_id("Persistent LAN") == "mac_ip"


def test_source_explicit_provider_capabilities():
    assert provider_multi_login("BSAE") is False
    assert provider_multi_login("Cisco") is False
    assert provider_multi_login("Quintum Tenor", "voip") is False
    assert provider_multi_login("GnuGk", "voip") is False
    assert provider_multi_login("Asterisk", "voip") is False
    assert provider_ip_assignment("ChilliSpot") is False
    assert provider_ip_assignment("Persistent LAN") is False


def test_unspecified_provider_capabilities_are_not_invented():
    assert provider_multi_login("Mikrotik") is None
    assert provider_ip_assignment("Mikrotik") is None


def test_provider_aliases_and_statuses():
    assert normalize_ras_type("Quintum Tenor") == "tenor"
    assert provider_profile("chilli spot").name == "chilli_spot"
    assert provider_supports_status("Mikrotik", "Alive")
    assert provider_supports_status("BSAE", "Start")


def test_provider_session_identity_uses_source_defined_keys():
    assert provider_session_id("Mikrotik", {"NAS-Port": "17", "Acct-Session-Id": "abc"}) == "17"
    assert provider_session_id("Total Control", {"USR-Interface-Index": "9", "Acct-Session-Id": "abc"}) == "9"
    assert provider_session_id("SER", {"Call-ID": "sip-123", "Acct-Session-Id": "abc"}) == "sip-123"
    assert provider_session_id("Cisco VPDN", {"Acct-Session-Id": "abc"}) == "abc"
