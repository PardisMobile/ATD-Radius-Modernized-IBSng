from atd_radius.domain.accounting_lifecycle import SessionAction
from atd_radius.domain.ras_provider_adapters import MIKROTIK_ADAPTER


def test_mikrotik_adapter_uses_nas_port_identity():
    assert MIKROTIK_ADAPTER.session_id({"NAS-Port": 42}) == "42"


def test_mikrotik_adapter_preserves_source_ip_assignment_rules():
    assert MIKROTIK_ADAPTER.ip_assignment({"NAS-Port-Type": "Ethernet"}) is True
    assert MIKROTIK_ADAPTER.ip_assignment({"NAS-Port-Type": "Virtual"}) is True
    assert MIKROTIK_ADAPTER.ip_assignment({"NAS-Port-Type": "Wireless-802.11"}) is False
    assert MIKROTIK_ADAPTER.ip_assignment({"NAS-Port-Type": "19"}) is False


def test_mikrotik_adapter_maps_source_traced_accounting():
    assert MIKROTIK_ADAPTER.accounting_action("Start") is SessionAction.INTERNET_UPDATE
    assert MIKROTIK_ADAPTER.accounting_action("Alive") is SessionAction.INTERNET_UPDATE
    assert MIKROTIK_ADAPTER.accounting_action("Stop") is SessionAction.INTERNET_STOP
