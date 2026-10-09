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


def test_external_adapter_registry_covers_only_source_traced_disconnect_families():
    from atd_radius.domain.ras_external import ExternalOperation
    from atd_radius.domain.ras_provider_adapters import (
        CHILLISPOT_EXTERNAL_ADAPTER,
        CISCO_EXTERNAL_ADAPTER,
        CISCO_VPDN_EXTERNAL_ADAPTER,
        MIKROTIK_EXTERNAL_ADAPTER,
        PORTMASTER_EXTERNAL_ADAPTER,
        PORTSLAVE_EXTERNAL_ADAPTER,
        PPPD_EXTERNAL_ADAPTER,
        TOTAL_CONTROL_EXTERNAL_ADAPTER,
    )

    expected = (
        (CHILLISPOT_EXTERNAL_ADAPTER, "provider-port", ExternalOperation.RADIUS_DISCONNECT),
        (CISCO_VPDN_EXTERNAL_ADAPTER, "rsh-interface", ExternalOperation.RSH),
        (MIKROTIK_EXTERNAL_ADAPTER, "rsh-port", ExternalOperation.RSH),
        (PORTMASTER_EXTERNAL_ADAPTER, "snmp-port", ExternalOperation.SNMP),
        (PORTSLAVE_EXTERNAL_ADAPTER, "launcher", ExternalOperation.LAUNCHER),
        (TOTAL_CONTROL_EXTERNAL_ADAPTER, "snmp-interface", ExternalOperation.SNMP),
        (PPPD_EXTERNAL_ADAPTER, "launcher", ExternalOperation.LAUNCHER),
    )
    for adapter, strategy, operation in expected:
        assert adapter.disconnect_strategy() == strategy
        request = adapter.disconnect_request({"source_key": "source-value"})
        assert request is not None
        assert request.operation is operation
        assert request.parameters["source_key"] == "source-value"

    assert CISCO_EXTERNAL_ADAPTER.disconnect_strategy() == "snmp-or-rsh"
    assert CISCO_EXTERNAL_ADAPTER.disconnect_request({"source_key": "source-value"}) is None


def test_providers_without_audited_disconnect_strategy_do_not_get_guessed_adapters():
    from atd_radius.domain.ras_provider import provider_disconnect_strategy
    from atd_radius.domain.ras_provider_adapters import ExternalSideEffectAdapter

    for provider in ("asterisk", "bsae", "gnugk", "mvts", "plan", "ser", "tenor"):
        assert provider_disconnect_strategy(provider) is None
        assert ExternalSideEffectAdapter(provider).disconnect_request(
            {"User-Name": "alice"}
        ) is None

def test_portmaster_adapter_builds_source_derived_snmp_disconnect():
    from atd_radius.domain.ras_provider_adapters import PORTMASTER_EXTERNAL_ADAPTER

    request = PORTMASTER_EXTERNAL_ADAPTER.source_disconnect_request(
        {"ras_ip": "192.0.2.10", "port": "7"}
    )
    assert request.operation.value == "snmp"
    assert request.parameters["set"]["oid"] == ".1.3.6.1.2.1.2.2.1.7.9"
    assert request.parameters["set"]["value"] == 2


def test_total_control_adapter_preserves_source_derived_snmp_cycle_order():
    from atd_radius.domain.ras_provider_adapters import TOTAL_CONTROL_EXTERNAL_ADAPTER

    request = TOTAL_CONTROL_EXTERNAL_ADAPTER.source_disconnect_request(
        {"ras_ip": "192.0.2.11", "interface_index": "42"}
    )
    assert request.operation.value == "snmp"
    assert [item["value"] for item in request.parameters["sets"]] == [2, 1]
    assert all(
        item["oid"] == ".1.3.6.1.2.1.2.2.1.7.42"
        for item in request.parameters["sets"]
    )

def test_portslave_adapter_builds_configured_launcher_call():
    from atd_radius.domain.ras_provider_adapters import PORTSLAVE_EXTERNAL_ADAPTER

    request = PORTSLAVE_EXTERNAL_ADAPTER.source_disconnect_request(
        {
            "command": "/configured/addons/portslave/kill",
            "ras_ip": "192.0.2.50",
            "port": "7",
        }
    )
    assert request.operation.value == "launcher"
    assert request.parameters["command"] == "/configured/addons/portslave/kill"
    assert request.parameters["arguments"] == ("192.0.2.50", "7")


def test_pppd_adapter_builds_source_derived_launcher_call():
    from atd_radius.domain.ras_provider_adapters import PPPD_EXTERNAL_ADAPTER

    request = PPPD_EXTERNAL_ADAPTER.source_disconnect_request(
        {
            "command": "/configured/addons/pppd/kill",
            "ras_ip": "192.0.2.51",
            "port": "ppp12",
        }
    )
    assert request.provider == "pppd"
    assert request.operation.value == "launcher"
    assert request.parameters["arguments"] == ("192.0.2.51", "ppp12")


def test_tenor_disconnect_cause_is_accounting_metadata_not_a_kill_operation():
    from atd_radius.domain.ras_provider import provider_disconnect_strategy
    from atd_radius.domain.ras_provider_adapters import QUINTUM_TENOR_EXTERNAL_ADAPTER

    assert provider_disconnect_strategy("tenor") is None
    assert QUINTUM_TENOR_EXTERNAL_ADAPTER.disconnect_request(
        {"disconnect_cause": "normal"}
    ) is None

