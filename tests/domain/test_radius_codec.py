from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import RadiusCodecError, decode, decrypt_user_password, encode, encrypt_user_password, encode_response, verify_control_request


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



def test_accounting_request_authenticator_is_verified():
    from hashlib import md5
    from atd_radius.domain.radius_codec import verify_accounting_request
    from struct import pack
    secret = b"shared"
    attrs = bytes((44, 5)) + b"sid"
    header = pack("!BBH", 4, 2, 20 + len(attrs))
    authenticator = md5(header + bytes(16) + attrs + secret).digest()
    wire = header + authenticator + attrs
    assert verify_accounting_request(wire, "shared")
    assert not verify_accounting_request(wire, "wrong")


def test_disconnect_and_coa_codes_round_trip():
    from atd_radius.domain.radius import RadiusCode, RadiusPacket
    from atd_radius.domain.radius_codec import decode, encode

    for code in (
        RadiusCode.DISCONNECT_REQUEST,
        RadiusCode.DISCONNECT_ACK,
        RadiusCode.DISCONNECT_NAK,
        RadiusCode.COA_REQUEST,
        RadiusCode.COA_ACK,
        RadiusCode.COA_NAK,
    ):
        packet = RadiusPacket(code, 7, {"User-Name": "alice"}, bytes(16))
        decoded = decode(encode(packet))
        assert decoded.code is code
        assert decoded.identifier == 7
        assert decoded.attributes["User-Name"] == "alice"


def test_control_request_authenticator_and_message_authenticator_are_verified():
    import hmac
    from hashlib import md5
    from atd_radius.domain.radius_codec import verify_control_request
    from struct import pack

    secret = b"shared"
    sid = bytes((44, 5)) + b"sid"
    msg = bytes((80, 18)) + bytes(16)
    header = pack("!BBH", 40, 7, 20 + len(sid) + len(msg))

    # RFC 5176: Message-Authenticator is calculated first with both
    # Request-Authenticator and Message-Authenticator treated as zero.
    ma_input = header + bytes(16) + sid + msg
    message_auth = hmac.new(secret, ma_input, "md5").digest()
    with_ma = header + bytes(16) + sid + bytes((80, 18)) + message_auth

    # The Request-Authenticator is then calculated like Accounting-Request.
    request_auth = md5(header + bytes(16) + sid + bytes((80, 18)) + message_auth + secret).digest()
    wire = header + request_auth + sid + bytes((80, 18)) + message_auth

    assert verify_control_request(wire, "shared")
    assert not verify_control_request(wire[:-1] + bytes((wire[-1] ^ 1,)), "shared")


def test_control_request_authenticator_is_valid_without_message_authenticator():
    from hashlib import md5
    from struct import pack
    secret = b"shared"
    attrs = bytes((44, 5)) + b"sid"
    header = pack("!BBH", 40, 3, 20 + len(attrs))
    auth = md5(header + bytes(16) + attrs + secret).digest()
    assert verify_control_request(header + auth + attrs, "shared")


def test_control_response_emits_message_authenticator_when_request_had_one():
    import hmac
    from hashlib import md5
    from struct import pack
    secret = "shared"
    sid = bytes((44, 5)) + b"sid"
    msg = bytes((80, 18)) + bytes(16)
    header = pack("!BBH", 40, 9, 20 + len(sid) + len(msg))
    request_ma = hmac.new(secret.encode(), header + bytes(16) + sid + msg, "md5").digest()
    request_auth = md5(header + bytes(16) + sid + bytes((80, 18)) + request_ma + secret.encode()).digest()
    request = RadiusPacket(RadiusCode.DISCONNECT_REQUEST, 9, {"Acct-Session-Id":"sid","Message-Authenticator":request_ma.hex()}, request_auth)
    response = RadiusPacket(RadiusCode.DISCONNECT_ACK, 9, {}, request_auth)
    wire = encode_response(response, request, secret)
    decoded = decode(wire, secret)
    assert len(decoded.attributes["Message-Authenticator"]) == 32
