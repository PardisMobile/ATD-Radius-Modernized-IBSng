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
