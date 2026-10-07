from atd_radius.domain.ras_provider import provider_sip_called_number, provider_sip_digest_attributes


def test_ser_called_number_is_derived_from_sip_req_uri():
    assert provider_sip_called_number({"Sip-Req-URI": "sip:00989121234567@example.test;user=phone"}) == "00989121234567"


def test_ser_called_number_falls_back_to_translated_uri():
    assert provider_sip_called_number({"Sip-Translated-Request-URI": "sip:44123@example.test"}) == "44123"


def test_ser_digest_consumption_is_source_scoped():
    attrs = {
        "Digest-Response": "r",
        "Digest-Attributes": "a",
        "Sip-User-ID": "u",
        "Sip-User-Realm": "realm",
        "Sip-User-Nonce": "nonce",
        "Sip-User-Method": "INVITE",
        "Sip-User-Digest-URI": "sip:bob@example.test",
        "Sip-User-Nonce-Count": "1",
        "Sip-User-QOP": "auth",
        "Sip-User-Opaque": "opaque",
        "Sip-User-Response": "response",
        "Sip-User-CNonce": "cnonce",
        "Unrelated": "must-not-leak",
    }
    result = provider_sip_digest_attributes(attrs)
    assert "Unrelated" not in result
    assert result["Sip-User-Method"] == "INVITE"
    assert len(result) == 12
