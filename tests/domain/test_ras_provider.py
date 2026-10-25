from atd_radius.domain.ras_provider import (
    normalize_ras_type,
    provider_ip_assignment,
    provider_multi_login,
    provider_profile,
    provider_supports_status,
    provider_unique_id,
    provider_session_id,
    provider_ip_assignment_for_attributes,
    provider_disconnect_strategy,
    RASProviderRegistry,
    PROVIDER_REGISTRY,
    provider_packet_context,
    provider_service_for_accounting,
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
    assert provider_supports_status("ChilliSpot", "Alive")


def test_provider_session_identity_uses_source_defined_keys():
    assert provider_session_id("Mikrotik", {"NAS-Port": "17", "Acct-Session-Id": "abc"}) == "17"
    assert provider_session_id("Total Control", {"USR-Interface-Index": "9", "Acct-Session-Id": "abc"}) == "9"
    assert provider_session_id("SER", {"Call-ID": "sip-123", "Acct-Session-Id": "abc"}) == "sip-123"
    assert provider_session_id("Cisco VPDN", {"Acct-Session-Id": "abc"}) == "abc"
    assert provider_session_id(
        "Cisco",
        {"NAS-Port-Type": "Async", "NAS-Port": "17", "Acct-Session-Id": "abc"},
    ) == "Async17"
    assert provider_session_id("Cisco", {"H323-Conf-ID": "h323-1", "NAS-Port": "17"}, service="voip") == "h323-1"


def test_bsae_provider_port_comes_from_user_name():
    assert provider_session_id(
        "BSAE",
        {"User-Name": "alice", "NAS-Port": "17", "Acct-Session-Id": "acct-1"},
    ) == "alice"


def test_mikrotik_ip_assignment_follows_a124_nas_port_type():
    assert provider_ip_assignment_for_attributes("Mikrotik", {"NAS-Port-Type": "Wireless-802.11"}) is False
    assert provider_ip_assignment_for_attributes("Mikrotik", {"NAS-Port-Type": "Ethernet"}) is True
    assert provider_ip_assignment_for_attributes("Mikrotik", {"NAS-Port-Type": "Virtual"}) is True


def test_chillispot_accepts_alive_and_exposes_provider_disconnect():
    assert provider_supports_status("ChilliSpot", "Alive") is True
    assert provider_supports_status("PortMaster", "Alive") is True
    assert provider_supports_status("PortSlave", "Alive") is True
    assert provider_supports_status("ChilliSpot", "Start") is True
    assert provider_disconnect_strategy("ChilliSpot") == "provider-port"


def test_provider_disconnect_strategies_are_source_derived():
    assert provider_disconnect_strategy("Cisco") == "snmp-or-rsh"
    assert provider_disconnect_strategy("Cisco VPDN") == "rsh-interface"
    assert provider_disconnect_strategy("PortMaster") == "snmp-port"
    assert provider_disconnect_strategy("PortSlave") == "launcher"
    assert provider_disconnect_strategy("PPPD") == "launcher"
    assert provider_disconnect_strategy("Quintum Tenor") is None


def test_provider_registry_facade_exposes_only_source_derived_behavior():
    registry = RASProviderRegistry()
    assert registry is not None
    assert registry.profile("Mikrotik").name == "mikrotik"
    assert registry.session_id("Mikrotik", {"NAS-Port": "17"}) == "17"
    assert registry.ip_assignment("Mikrotik", {"NAS-Port-Type": "Wireless-802.11"}) is False
    assert registry.supports_status("ChilliSpot", "Alive") is True
    assert registry.disconnect_strategy("Cisco") == "snmp-or-rsh"
    assert registry.sip_called_number({"Sip-Req-URI": "sip:12345@example.net;user=phone"}) == "12345"
    assert PROVIDER_REGISTRY.profile("Total Control").unique_id == "interface_index"


def test_provider_packet_context_is_side_effect_free_and_source_derived():
    ctx = provider_packet_context(
        "Cisco",
        {"H323-Conf-ID": "h323-42", "NAS-Port": "17"},
        service="voip",
        accounting_status="Alive",
    )
    assert ctx is not None
    assert ctx.profile.name == "cisco"
    assert ctx.service == "voip"
    assert ctx.session_id == "h323-42"
    assert ctx.multi_login is False
    assert ctx.accounting_supported is True
    assert ctx.disconnect_strategy == "snmp-or-rsh"


def test_provider_packet_context_preserves_bsae_user_name_identity():
    ctx = provider_packet_context(
        "BSAE",
        {"User-Name": "alice", "NAS-Port": "17"},
        accounting_status="Start",
    )
    assert ctx is not None
    assert ctx.session_id == "alice"
    assert ctx.multi_login is False
    assert ctx.accounting_supported is True


def test_provider_packet_context_rejects_unverified_status_without_side_effect():
    ctx = provider_packet_context(
        "Cisco",
        {"NAS-Port": "17"},
        accounting_status="Not-A-Status",
    )
    assert ctx is not None
    assert ctx.accounting_supported is False

def test_cisco_accounting_service_uses_source_framed_protocol_discriminator():
    assert provider_service_for_accounting("Cisco", {"Framed-Protocol": "PPP"}) == "internet"
    assert provider_service_for_accounting("Cisco", {"Framed-Protocol": ["PPP"]}) == "internet"
    assert provider_service_for_accounting("Cisco", {"H323-Conf-ID": "call-42"}) == "voip"
    assert provider_service_for_accounting("MVTS", {"Framed-Protocol": "PPP"}) == "voip"



def test_cisco_voip_accounting_action_guards_follow_a124_call_leg_rules():
    from atd_radius.domain.ras_provider import provider_accounting_should_apply

    assert provider_accounting_should_apply(
        "Cisco", "voip", "Start",
        {"H323-call-type": "VoIP", "H323-call-origin": "originate"},
    )
    assert provider_accounting_should_apply(
        "Cisco", "voip", "Stop",
        {"H323-call-type": "VoIP", "H323-call-origin": "originate"},
    )
    assert not provider_accounting_should_apply(
        "Cisco", "voip", "Start",
        {"H323-call-type": "Telephony", "H323-call-origin": "answer"},
    )
    assert not provider_accounting_should_apply(
        "Cisco", "voip", "Stop",
        {"H323-call-type": "Telephony", "H323-call-origin": "answer", "H323-Conf-ID": "call"},
    )
    assert not provider_accounting_should_apply(
        "Cisco", "voip", "Alive",
        {"H323-call-type": "VoIP", "H323-call-origin": "originate"},
    )
    assert provider_accounting_should_apply(
        "Cisco", "internet", "Start", {"Framed-Protocol": "PPP"}
    )



def test_cisco_internet_identity_matches_source_port_resolution():
    assert provider_session_id(
        "Cisco", {"Cisco-NAS-Port": ["Async0/1 extra"], "Acct-Session-Id": ["acct-1"]}
    ) == "Async0/1"
    assert provider_session_id(
        "Cisco", {"NAS-Port-Type": ["Async"], "NAS-Port": ["3"], "Acct-Session-Id": ["acct-2"]}
    ) == "Async3"


def test_cisco_h323_wire_values_are_decoded_before_identity_and_leg_checks():
    from atd_radius.domain.ras_provider import provider_accounting_should_apply

    assert provider_session_id(
        "Cisco", {"H323-Conf-ID": ["H323-conf-id=call-42"]}, service="voip"
    ) == "call-42"
    attrs = {
        "H323-call-type": ["H323-call-type=VoIP"],
        "H323-call-origin": ["H323-call-origin=originate"],
    }
    # The source VoIPRas.getH323AttrValue strips the name prefix before
    # Cisco's Start/Stop call-leg comparisons.
    assert provider_accounting_should_apply("Cisco", "voip", "Start", attrs)
    assert provider_accounting_should_apply("Cisco", "voip", "Stop", attrs)



def test_cisco_call_leg_guard_decodes_source_wire_values():
    from atd_radius.domain.ras_provider import provider_accounting_should_apply

    assert provider_accounting_should_apply(
        "Cisco", "voip", "Start",
        {
            "H323-call-type": ["H323-call-type=VoIP"],
            "H323-call-origin": ["H323-call-origin=originate"],
        },
    )
    assert not provider_accounting_should_apply(
        "Cisco", "voip", "Start",
        {
            "H323-call-type": ["H323-call-type=Telephony"],
            "H323-call-origin": ["H323-call-origin=answer"],
        },
    )


def test_cisco_voip_accounting_username_uses_configured_prefix_length():
    from atd_radius.domain.ras_provider import provider_accounting_username

    assert provider_accounting_username(
        "Cisco", "voip", "voipuserSecret", {"cisco_voip_username_length": "8"}
    ) == "voipuser"
    assert provider_accounting_username(
        "Cisco", "internet", "voipuserSecret", {"cisco_voip_username_length": 8}
    ) == "voipuserSecret"
    assert provider_accounting_username("MVTS", "voip", "alice") == "alice"



def test_cisco_telephony_answer_stop_requires_successful_pre_auth_membership():
    from atd_radius.domain.ras_provider import provider_accounting_should_apply

    attrs = {
        "H323-call-type": ["H323-call-type=Telephony"],
        "H323-call-origin": ["H323-call-origin=answer"],
        "H323-conf-id": ["H323-conf-id=auth-call-1"],
    }
    assert not provider_accounting_should_apply("Cisco", "voip", "Stop", attrs)
    assert provider_accounting_should_apply(
        "Cisco", "voip", "Stop", attrs, {"auth-call-1"}
    )
    assert not provider_accounting_should_apply(
        "Cisco", "voip", "Stop", attrs, {"different-call"}
    )



def test_cisco_alive_never_enters_normal_accounting_lifecycle():
    from atd_radius.domain.ras_provider import provider_accounting_should_apply

    assert not provider_accounting_should_apply(
        "Cisco", "internet", "Alive", {"Framed-Protocol": "PPP"}
    )
    assert not provider_accounting_should_apply(
        "Cisco", "voip", "Alive",
        {
            "H323-call-type": "H323-call-type=VoIP",
            "H323-call-origin": "H323-call-origin=originate",
        },
    )



def test_cisco_session_identity_fails_closed_when_source_identity_is_missing():
    # Cisco VoIP is keyed by H.323 conference ID, never NAS-Port or Acct-Session-Id.
    assert provider_session_id(
        "Cisco", {"NAS-Port": ["17"], "Acct-Session-Id": ["acct-1"]}, service="voip"
    ) is None
    # Cisco Internet is keyed by Cisco-NAS-Port or NAS-Port-Type + NAS-Port.
    assert provider_session_id(
        "Cisco", {"Acct-Session-Id": ["acct-1"]}, service="internet"
    ) is None


def test_cisco_voip_does_not_treat_acct_session_id_as_h323_conf_id():
    assert provider_session_id(
        "Cisco",
        {"Acct-Session-Id": ["acct-1"], "NAS-Port": ["17"]},
        service="voip",
    ) is None

def test_source_login_identity_normalization_is_provider_specific():
    from atd_radius.domain.ras_provider import provider_login_identity

    assert provider_login_identity(
        "Mikrotik",
        {"NAS-Port-Type": "Ethernet", "Calling-Station-Id": "AA:BB:CC:DD:EE:FF"},
    ) == {"mac": "AA:BB:CC:DD:EE:FF"}
    assert provider_login_identity(
        "Mikrotik",
        {"NAS-Port-Type": "Virtual", "Calling-Station-Id": "192.0.2.25"},
    ) == {"station_ip": "192.0.2.25"}
    assert provider_login_identity(
        "Mikrotik",
        {"NAS-Port-Type": "5", "Calling-Station-Id": "192.0.2.26"},
    ) == {"station_ip": "192.0.2.26"}
    assert provider_login_identity(
        "Mikrotik",
        {"NAS-Port-Type": "Wireless-802.11", "Calling-Station-Id": "AA:BB"},
    ) == {"mac": "AA:BB"}
    assert provider_login_identity(
        "PPPD", {"Calling-Station-Id": "192.0.2.25"}
    ) == {"station_ip": "192.0.2.25"}
    assert provider_login_identity(
        "ChilliSpot", {"Calling-Station-Id": "AA:BB:CC:DD:EE:FF"}
    ) == {"mac": "AA:BB:CC:DD:EE:FF"}
    assert provider_login_identity(
        "BSAE", {"Calling-Station-Id": "AABBCCDDEEFF-extra"}
    ) == {"mac": "AA:BB:CC:DD:EE:FF"}
    assert provider_login_identity(
        "Unknown", {"Calling-Station-Id": "AA:BB:CC:DD:EE:FF"}
    ) == {}

