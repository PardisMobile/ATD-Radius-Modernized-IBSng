from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import RadiusCodecError, decode, decrypt_user_password, encode, encrypt_user_password


def test_common_attributes_round_trip():
    auth = bytes.fromhex("00112233445566778899aabbccddeeff")
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST, 7,
        {"User-Name":"alice","NAS-IP-Address":"192.0.2.10","NAS-Port":"12"},
        auth,
    )
    decoded = decode(encode(packet))
    assert decoded.code is RadiusCode.ACCESS_REQUEST
    assert decoded.identifier == 7
    assert decoded.attributes == packet.attributes


def test_pap_password_round_trip():
    auth = bytes.fromhex("00112233445566778899aabbccddeeff")
    encrypted = encrypt_user_password("s3cret", "shared", auth)
    assert len(encrypted) == 16
    assert decrypt_user_password(encrypted, "shared", auth) == "s3cret"


def test_password_attribute_uses_shared_secret():
    auth = bytes.fromhex("00112233445566778899aabbccddeeff")
    packet = RadiusPacket(RadiusCode.ACCESS_REQUEST, 3, {"User-Name":"alice","User-Password":"secret"}, auth)
    assert decode(encode(packet, "shared"), "shared").attributes["User-Password"] == "secret"


def test_malformed_attribute_is_rejected():
    wire = bytearray(encode(RadiusPacket(RadiusCode.ACCESS_REQUEST, 1, {}, bytes(16))) + bytes((1, 1)))
    wire[2:4] = (22).to_bytes(2, "big")
    try:
        decode(wire)
    except RadiusCodecError:
        return
    raise AssertionError("malformed attribute was accepted")



def test_response_authenticator_is_derived_from_request():
    from hashlib import md5
    from atd_radius.domain.radius_codec import encode_response
    request = RadiusPacket(
        RadiusCode.ACCESS_REQUEST, 9, {"User-Name":"alice"},
        bytes.fromhex("00112233445566778899aabbccddeeff"),
    )
    response = RadiusPacket(RadiusCode.ACCESS_ACCEPT, 9, {"Reply-Message":"ok"}, request.authenticator)
    wire = encode_response(response, request, "shared")
    expected = md5(wire[:4] + request.authenticator + wire[20:] + b"shared").digest()
    assert wire[4:20] == expected
