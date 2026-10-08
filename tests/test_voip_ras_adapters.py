from atd_radius.domain.ras_provider_adapters import (
    ASTERISK_ADAPTER,
    GNUGK_ADAPTER,
    MVTS_ADAPTER,
    QUINTUM_TENOR_ADAPTER,
)


def test_asterisk_multi_login_is_attribute_controlled():
    assert ASTERISK_ADAPTER.multi_login({}) is False
    assert ASTERISK_ADAPTER.multi_login({"asterisk_multi_login": "0"}) is False
    assert ASTERISK_ADAPTER.multi_login({"asterisk_multi_login": "1"}) is True


def test_gnugk_multi_login_is_attribute_controlled():
    assert GNUGK_ADAPTER.multi_login({}) is False
    assert GNUGK_ADAPTER.multi_login({"gnugk_multiple_login": "0"}) is False
    assert GNUGK_ADAPTER.multi_login({"gnugk_multiple_login": "2"}) is True


def test_mvts_and_tenor_keep_source_identities():
    assert MVTS_ADAPTER.session_id({"h323-conf-id": "mvts-1"}) == "mvts-1"
    assert QUINTUM_TENOR_ADAPTER.session_id({"h323-conf-id": "tenor-1"}) == "tenor-1"
    assert QUINTUM_TENOR_ADAPTER.multi_login() is False
    assert QUINTUM_TENOR_ADAPTER.single_session_h323() is True
