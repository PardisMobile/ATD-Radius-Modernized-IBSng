from atd_radius.domain.accounting_lifecycle import SessionAction
from atd_radius.domain.ras_provider import provider_accounting_action


def test_internet_provider_start_alive_stop_map_to_native_actions():
    for provider in ("MikroTik", "BSAE", "ChilliSpot", "Cisco", "Cisco VPDN", "PortMaster", "PortSlave", "Total Control"):
        assert provider_accounting_action(provider, "Start") is SessionAction.INTERNET_UPDATE
        assert provider_accounting_action(provider, "Alive") is SessionAction.INTERNET_UPDATE
        assert provider_accounting_action(provider, "Stop") is SessionAction.INTERNET_STOP


def test_persistent_lan_uses_persistent_lan_actions():
    assert provider_accounting_action("Persistent LAN", "Start", "persistent_lan") is SessionAction.PERSISTENT_LAN_AUTHENTICATE
    assert provider_accounting_action("Persistent LAN", "Stop", "persistent_lan") is SessionAction.PERSISTENT_LAN_STOP


def test_unsupported_provider_or_status_is_not_mapped():
    assert provider_accounting_action("unknown", "Start") is None
    assert provider_accounting_action("MikroTik", "Interim-Update") is None


def test_voip_mapping_is_not_guessed():
    assert provider_accounting_action("Cisco", "Start", "voip") is None
    assert provider_accounting_action("SER", "Alive", "voip") is None


def test_voip_only_profiles_do_not_inherit_internet_actions():
    for provider in ("Asterisk", "GnuGk", "MVTS", "SER", "Quintum Tenor"):
        assert provider_accounting_action(provider, "Start", "internet") is None
        assert provider_accounting_action(provider, "Stop", "internet") is None
