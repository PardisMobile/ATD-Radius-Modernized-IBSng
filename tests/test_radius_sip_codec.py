from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import decode, decode_sip, encode, encode_sip


def test_sip_context_preserves_core_101_collision():
    packet = RadiusPacket(
        RadiusCode.ACCOUNTING_REQUEST,
        7,
        {
            "Sip-Method": 1,
            "Sip-Response-Code": 2,
            "Sip-Source-IP-Address": "192.0.2.10",
            "Sip-Source-Port": 5060,
            "Sip-User-ID": "alice",
            "Sip-User-Realm": "example.test",
            "Sip-User-Nonce": "nonce",
            "Sip-User-Method": "INVITE",
            "Sip-User-Digest-URI": "sip:bob@example.test",
            "Sip-User-Nonce-Count": "00000001",
            "Sip-User-QOP": "auth",
            "Sip-User-Opaque": "opaque",
            "Sip-User-Response": "response",
            "Sip-User-CNonce": "cnonce",
            "Sip-URI-User": "bob",
            "Sip-Req-URI": "sip:bob@example.test",
            "Sip-Group": "sales",
            "Sip-CC": "cc-1",
            "Sip-RPId": "rpid-1",
            "SIP-AVP": "category:prepaid",
        },
        bytes(16),
    )
    wire = encode_sip(packet)
    decoded = decode_sip(wire)

    assert decoded.attributes["Sip-Method"] == "1"
    assert decoded.attributes["Sip-Response-Code"] == "2"
    assert decoded.attributes["Sip-Source-IP-Address"] == "192.0.2.10"
    assert decoded.attributes["Sip-Source-Port"] == "5060"
    assert decoded.attributes["Sip-User-Method"] == "INVITE"
    assert decoded.attributes["Sip-Req-URI"] == "sip:bob@example.test"

    core = RadiusPacket(RadiusCode.DISCONNECT_NAK, 7, {"Error-Cause": 401}, bytes(16))
    assert decode(encode(core)).attributes["Error-Cause"] == "401"


def test_sip_digest_attributes_use_wire_numbers_without_internal_1063_plus():
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        8,
        {
            "Digest-Response": "deadbeef",
            "Digest-Attributes": "realm=example.test",
        },
        bytes(16),
    )
    wire = encode_sip(packet)
    decoded = decode_sip(wire)

    assert decoded.attributes == packet.attributes
    assert b"\x06\x00" not in wire



def test_sip_dictionary_wire_numbers_and_source_types():
    packet = RadiusPacket(
        RadiusCode.ACCOUNTING_REQUEST,
        9,
        {
            "Sip-CSeq": "42 INVITE",
            "Sip-To-Tag": "to-tag",
            "Sip-From-Tag": "from-tag",
            "Sip-Branch-ID": "z9hG4bK",
            "Sip-Translated-Request-URI": "sip:translated@example.test",
            "Sip-Source-IP-Address": "198.51.100.8",
            "Sip-Source-Port": 5061,
            "Sip-User-ID": "alice",
            "Sip-User-Realm": "example.test",
            "Sip-User-Nonce": "nonce",
            "Sip-User-Method": "INVITE",
            "Sip-User-Digest-URI": "sip:bob@example.test",
            "Sip-User-Nonce-Count": "00000001",
            "Sip-User-QOP": "auth",
            "Sip-User-Opaque": "opaque",
            "Sip-User-Response": "response",
            "Sip-User-CNonce": "cnonce",
            "Digest-Response": "digest",
            "Sip-URI-User": "bob",
            "Sip-Req-URI": "sip:bob@example.test",
            "Sip-Group": "sales",
            "Sip-CC": "cc-1",
            "Sip-RPId": "rpid-1",
            "SIP-AVP": "category:prepaid",
        },
        bytes(16),
    )
    wire = encode_sip(packet)
    decoded = decode_sip(wire)

    # A1.24 dictionary.ser / dictionary.sip assignments; 108 is IPv4 and
    # 109 is an integer, while the adjacent digest/tag fields are strings.
    expected_numbers = {
        "Sip-CSeq": 103,
        "Sip-To-Tag": 104,
        "Sip-From-Tag": 105,
        "Sip-Branch-ID": 106,
        "Sip-Translated-Request-URI": 107,
        "Sip-Source-IP-Address": 108,
        "Sip-Source-Port": 109,
        "Sip-User-ID": 110,
        "Sip-User-Realm": 111,
        "Sip-User-Nonce": 112,
        "Sip-User-Method": 113,
        "Sip-User-Digest-URI": 114,
        "Sip-User-Nonce-Count": 115,
        "Sip-User-QOP": 116,
        "Sip-User-Opaque": 117,
        "Sip-User-Response": 118,
        "Sip-User-CNonce": 119,
        "Digest-Response": 206,
        "Sip-URI-User": 208,
        "Sip-Req-URI": 210,
        "Sip-Group": 211,
        "Sip-CC": 212,
        "Sip-RPId": 213,
        "SIP-AVP": 225,
    }
    offset = 20
    observed = {}
    while offset < len(wire):
        number, length = wire[offset], wire[offset + 1]
        observed[number] = wire[offset + 2 : offset + length]
        offset += length

    for name, number in expected_numbers.items():
        assert number in observed, name
    assert observed[108] == bytes((198, 51, 100, 8))
    assert len(observed[109]) == 4
    assert observed[109] == b"\x00\x00\x13\xC5"
    assert observed[103] == b"42 INVITE"
    assert decoded.attributes["Sip-Source-Port"] == "5061"
    assert decoded.attributes["Sip-Branch-ID"] == "z9hG4bK"
    assert decoded.attributes["Digest-Response"] == "digest"
