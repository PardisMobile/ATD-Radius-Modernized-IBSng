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
