from atd_radius.domain.accounting_lifecycle import SessionAction
from atd_radius.domain.ras_provider_adapters import PERSISTENT_LAN_ADAPTER, SER_ADAPTER


def test_persistent_lan_adapter_is_explicitly_non_ip_assigning():
    assert PERSISTENT_LAN_ADAPTER.ip_assignment() is False
    assert PERSISTENT_LAN_ADAPTER.persistent_lan() is True
    assert PERSISTENT_LAN_ADAPTER.session_id({"mac_ip": "aa:bb:cc:dd:ee:ff/192.0.2.10"}) == "aa:bb:cc:dd:ee:ff/192.0.2.10"


def test_persistent_lan_adapter_uses_native_actions():
    assert PERSISTENT_LAN_ADAPTER.accounting_action("Start") is SessionAction.PERSISTENT_LAN_AUTHENTICATE
    assert PERSISTENT_LAN_ADAPTER.accounting_action("Stop") is SessionAction.PERSISTENT_LAN_STOP
    assert PERSISTENT_LAN_ADAPTER.accounting_action("Alive") is None


def test_ser_adapter_preserves_source_traced_sip_identity_and_actions():
    attrs = {
        "Sip-Call-ID": "call-123",
        "Sip-Req-URI": "sip:09120000000@example.test",
        "Digest-Response": "digest",
    }
    assert SER_ADAPTER.session_id(attrs) == "call-123"
    assert SER_ADAPTER.called_number(attrs) == "09120000000"
    assert SER_ADAPTER.digest_attributes(attrs) == {"Digest-Response": "digest"}
    assert SER_ADAPTER.multi_login() is None
    assert SER_ADAPTER.accounting_action("Start") is SessionAction.VOIP_AUTHENTICATE
    assert SER_ADAPTER.accounting_action("Stop") is SessionAction.VOIP_STOP
    assert SER_ADAPTER.accounting_action("Alive") is None


def test_external_adapters_preserve_source_traced_strategy_only():
    from atd_radius.domain.ras_external import ExternalOperation
    from atd_radius.domain.ras_provider_adapters import (
        CHILLISPOT_EXTERNAL_ADAPTER,
        CISCO_EXTERNAL_ADAPTER,
        CISCO_VPDN_EXTERNAL_ADAPTER,
        PORTMASTER_EXTERNAL_ADAPTER,
        PORTSLAVE_EXTERNAL_ADAPTER,
        TOTAL_CONTROL_EXTERNAL_ADAPTER,
    )

    assert CHILLISPOT_EXTERNAL_ADAPTER.disconnect_strategy() == "provider-port"
    assert CHILLISPOT_EXTERNAL_ADAPTER.disconnect_request(
        {"User-Name": "alice"}
    ).operation is ExternalOperation.RADIUS_DISCONNECT

    assert CISCO_VPDN_EXTERNAL_ADAPTER.disconnect_strategy() == "rsh-interface"
    assert CISCO_VPDN_EXTERNAL_ADAPTER.disconnect_request(
        {"interface": 12}
    ).operation is ExternalOperation.RSH

    assert PORTMASTER_EXTERNAL_ADAPTER.disconnect_request(
        {"port": 7}
    ).operation is ExternalOperation.SNMP
    assert PORTSLAVE_EXTERNAL_ADAPTER.disconnect_request(
        {"ras_ip": "203.0.113.10", "port": 7}
    ).operation is ExternalOperation.LAUNCHER
    assert TOTAL_CONTROL_EXTERNAL_ADAPTER.disconnect_request(
        {"interface_index": 42}
    ).operation is ExternalOperation.SNMP

    assert CISCO_EXTERNAL_ADAPTER.disconnect_strategy() == "snmp-or-rsh"
    assert CISCO_EXTERNAL_ADAPTER.disconnect_request({"port": 7}) is None
