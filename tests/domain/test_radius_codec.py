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
        RadiusCode.DISCONNECT_REQUEST, RadiusCode.DISCONNECT_ACK, RadiusCode.DISCONNECT_NAK,
        RadiusCode.COA_REQUEST, RadiusCode.COA_ACK, RadiusCode.COA_NAK,
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
    ma_input = header + bytes(16) + sid + msg
    message_auth = hmac.new(secret, ma_input, "md5").digest()
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


def test_chap_and_mschapv2_attributes_round_trip_as_wire_values():
    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    mschapv2_response = b"\x07\x00" + peer_challenge + b"\x00" * 8 + nt_response
    chap_response = bytes.fromhex("01" + "00112233445566778899aabbccddeeff")

    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        11,
        {
            "User-Name": "User",
            "CHAP-Password": chap_response,
            "CHAP-Challenge": auth_challenge,
            "MS-CHAP-Challenge": auth_challenge,
            "MS-CHAP2-Response": mschapv2_response,
        },
        bytes.fromhex("00112233445566778899aabbccddeeff"),
    )
    decoded = decode(encode(packet))
    assert decoded.attributes["CHAP-Password"] == chap_response.hex()
    assert decoded.attributes["CHAP-Challenge"] == auth_challenge.hex()
    assert decoded.attributes["MS-CHAP-Challenge"] == auth_challenge.hex()
    assert decoded.attributes["MS-CHAP2-Response"] == mschapv2_response.hex()


def test_mschapv2_vsa_rejects_noncanonical_response_length():
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        12,
        {"MS-CHAP2-Response": b"\x00" * 49},
        bytes(16),
    )
    try:
        encode(packet)
    except RadiusCodecError:
        return
    raise AssertionError("non-canonical MS-CHAP2-Response was accepted")


def test_mschapv2_success_vsa_round_trip():
    success = "S=407A5589115FD0D6209F510FE9C04566932CDA56"
    packet = RadiusPacket(
        RadiusCode.ACCESS_ACCEPT,
        13,
        {"MS-CHAP2-Success": success},
        bytes(16),
    )
    decoded = decode(encode(packet))
    assert decoded.attributes["MS-CHAP2-Success"] == success


def test_mppe_keys_are_salted_and_rfc2548_encrypted():
    from hashlib import md5
    from struct import unpack
    from atd_radius.domain.radius_auth import derive_mschapv2_mppe_keys

    request_authenticator = bytes.fromhex("00112233445566778899aabbccddeeff")
    send_key, recv_key = derive_mschapv2_mppe_keys(
        "clientPass",
        bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF"),
    )
    packet = RadiusPacket(
        RadiusCode.ACCESS_ACCEPT,
        14,
        {
            "MS-MPPE-Send-Key": send_key,
            "MS-MPPE-Recv-Key": recv_key,
        },
        request_authenticator,
    )
    wire = encode(packet, "shared")
    offset = 20
    decoded = {}
    salts = []
    while offset < len(wire):
        length = wire[offset + 1]
        value = wire[offset + 2 : offset + length]
        assert value[:4] == (311).to_bytes(4, "big")
        vendor_type = value[4]
        vendor_length = value[5]
        assert vendor_length == len(value) - 4
        salt = value[6:8]
        ciphertext = value[8:4 + vendor_length]
        salts.append(salt)
        previous = md5(b"shared" + request_authenticator + salt).digest()
        plaintext = bytearray(a ^ b for a, b in zip(ciphertext[:16], previous))
        for block_offset in range(16, len(ciphertext), 16):
            previous = md5(b"shared" + bytes(plaintext[block_offset - 16:block_offset])).digest()
            plaintext.extend(
                a ^ b
                for a, b in zip(ciphertext[block_offset:block_offset + 16], previous)
            )
        key_length = plaintext[0]
        decoded[vendor_type] = bytes(plaintext[1:1 + key_length])
        offset += length
    assert salts[0] != salts[1]
    assert salts[0][0] & 0x80
    assert salts[1][0] & 0x80
    assert decoded[16] == send_key
    assert decoded[17] == recv_key
