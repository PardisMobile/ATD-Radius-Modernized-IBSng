import pytest

from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import RadiusCodecError, decode, decrypt_user_password, encode, encrypt_user_password, encode_response, verify_control_request, verify_message_authenticator


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
    assert not verify_accounting_request(wire + bytes((0,)), "shared")


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


def test_access_request_message_authenticator_is_verified():
    import hmac
    from struct import pack
    secret = b"shared"
    attrs = bytes((1, 7)) + b"alice" + bytes((80, 18)) + bytes(16)
    header = pack("!BBH", 1, 21, 20 + len(attrs))
    request_auth = bytes.fromhex("00112233445566778899aabbccddeeff")
    wire = header + request_auth + attrs
    ma_offset = 29
    message_auth = hmac.new(secret, wire[:ma_offset] + bytes(16) + wire[ma_offset + 16:], "md5").digest()
    wire = wire[:ma_offset] + message_auth + wire[ma_offset + 16:]
    assert verify_message_authenticator(wire, "shared")
    assert not verify_message_authenticator(wire[:-1] + bytes((wire[-1] ^ 1,)), "shared")


def test_access_response_emits_message_authenticator_when_request_had_one():
    import hmac
    from hashlib import md5
    from struct import pack
    secret = "shared"
    request_auth = bytes.fromhex("00112233445566778899aabbccddeeff")
    attrs = bytes((1, 7)) + b"alice" + bytes((80, 18)) + bytes(16)
    header = pack("!BBH", 1, 22, 20 + len(attrs))
    wire = header + request_auth + attrs
    ma_offset = 29
    request_ma = hmac.new(secret.encode(), wire[:ma_offset] + bytes(16) + wire[ma_offset + 16:], "md5").digest()
    wire = wire[:ma_offset] + request_ma + wire[ma_offset + 16:]
    request = decode(wire)
    response = RadiusPacket(RadiusCode.ACCESS_ACCEPT, 22, {"Reply-Message": "ok"}, request.authenticator)
    response_wire = encode_response(response, request, secret)
    response_attrs = decode(response_wire, secret).attributes
    assert len(response_attrs["Message-Authenticator"]) == 32
    assert verify_message_authenticator(
        response_wire[:4] + request.authenticator + response_wire[20:], secret
    )
    expected = md5(response_wire[:4] + request.authenticator + response_wire[20:] + secret.encode()).digest()
    assert response_wire[4:20] == expected


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
            previous = md5(b"shared" + ciphertext[block_offset - 16:block_offset]).digest()
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

def test_mschapv1_mppe_key_and_policy_vsas_are_a124_encrypted():
    from atd_radius.domain.radius_auth import derive_mschapv1_mppe_key
    from atd_radius.domain.radius_codec import _crypt_password

    request_authenticator = bytes.fromhex("00112233445566778899aabbccddeeff")
    key = derive_mschapv1_mppe_key("clientPass")
    packet = RadiusPacket(
        RadiusCode.ACCESS_ACCEPT,
        15,
        {
            "MS-CHAP-MPPE-Keys": key,
            "MS-MPPE-Encryption-Policy": "00000001",
            "MS-MPPE-Encryption-Types": "00000006",
        },
        request_authenticator,
    )
    wire = encode(packet, "shared")
    decoded = decode(wire, "shared")
    assert decoded.attributes["MS-CHAP-MPPE-Keys"] == _crypt_password(
        key, b"shared", request_authenticator
    ).hex()
    assert decoded.attributes["MS-MPPE-Encryption-Policy"] == "00000001"
    assert decoded.attributes["MS-MPPE-Encryption-Types"] == "00000006"


def test_a124_core_dictionary_extended_attributes_round_trip():
    packet = RadiusPacket(
        RadiusCode.ACCESS_ACCEPT,
        16,
        {
            "Framed-Compression": "1",
            "Login-IP-Host": "192.0.2.20",
            "Login-Service": "3",
            "Login-TCP-Port": "23",
            "Framed-Route": "192.0.2.0/24",
            "Acct-Input-Gigawords": "2",
            "Acct-Output-Gigawords": "3",
            "Event-Timestamp": "1700000000",
            "Acct-Interim-Interval": "300",
            "EAP-Message": "01020304",
            "Framed-IPv6-Prefix": "20010db8000000000000000000000000",
        },
        bytes(16),
    )
    decoded = decode(encode(packet))
    assert decoded.attributes["Framed-Compression"] == "1"
    assert decoded.attributes["Login-IP-Host"] == "192.0.2.20"
    assert decoded.attributes["Login-Service"] == "3"
    assert decoded.attributes["Login-TCP-Port"] == "23"
    assert decoded.attributes["Acct-Input-Gigawords"] == "2"
    assert decoded.attributes["Acct-Output-Gigawords"] == "3"
    assert decoded.attributes["Event-Timestamp"] == "1700000000"
    assert decoded.attributes["Acct-Interim-Interval"] == "300"
    assert decoded.attributes["EAP-Message"] == "01020304"
    assert decoded.attributes["Framed-IPv6-Prefix"] == "20010db8000000000000000000000000"


def test_microsoft_dns_vendor_attributes_round_trip():
    packet = RadiusPacket(
        RadiusCode.ACCESS_ACCEPT,
        17,
        {
            "MS-Primary-DNS-Server": "1.1.1.1",
            "MS-Secondary-DNS-Server": "8.8.8.8",
            "MS-CHAP-Error": "E=691 R=0",
        },
        bytes(16),
    )
    decoded = decode(encode(packet, "shared"), "shared")
    assert decoded.attributes["MS-Primary-DNS-Server"] == "1.1.1.1"
    assert decoded.attributes["MS-Secondary-DNS-Server"] == "8.8.8.8"
    assert decoded.attributes["MS-CHAP-Error"] == "E=691 R=0"


def test_provider_vsa_round_trip():
    packet = RadiusPacket(
        RadiusCode.ACCOUNTING_REQUEST,
        18,
        {"H323-conf-id": "session-a", "Rate-Limit": "10M/10M", "Recv-Limit": "1000"},
        bytes(16),
    )
    decoded = decode(encode(packet))
    assert decoded.attributes["H323-conf-id"] == "session-a"
    assert decoded.attributes["Rate-Limit"] == "10M/10M"
    assert decoded.attributes["Recv-Limit"] == "1000"


def test_a124_usr_interface_index_vendor_vsa_round_trip():
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        19,
        {"USR-Interface-Index": "37"},
        bytes(16),
    )
    wire = encode(packet)
    value = wire[22:]
    assert value[:4] == (429).to_bytes(4, "big")
    assert value[4:8] == (0x9843).to_bytes(4, "big")
    assert value[8:] == (37).to_bytes(4, "big")
    decoded = decode(wire)
    assert decoded.attributes["USR-Interface-Index"] == "37"


def test_outbound_disconnect_request_authenticator_is_encoded_and_verified():
    from atd_radius.domain.radius_codec import encode_control_request

    packet = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST,
        37,
        {"User-Name": "alice"},
        bytes(16),
    )
    wire = encode_control_request(packet, "shared")
    assert wire[0] == 40
    assert decode(wire, "shared").attributes["User-Name"] == "alice"
    assert verify_control_request(wire, "shared")
    assert not verify_control_request(wire, "wrong")


def test_outbound_control_request_message_authenticator_is_recomputed():
    from atd_radius.domain.radius_codec import encode_control_request

    packet = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST,
        38,
        {"User-Name": "alice", "Message-Authenticator": "ff" * 16},
        bytes(16),
    )
    wire = encode_control_request(packet, "shared")
    decoded = decode(wire, "shared")
    assert decoded.attributes["Message-Authenticator"] != "ff" * 16
    assert verify_control_request(wire, "shared")


def test_outbound_control_encoder_rejects_non_control_packets():
    from atd_radius.domain.radius_codec import encode_control_request

    packet = RadiusPacket(RadiusCode.ACCESS_REQUEST, 39, {"User-Name": "alice"}, bytes(16))
    try:
        encode_control_request(packet, "shared")
    except RadiusCodecError:
        return
    raise AssertionError("non-control request was accepted by control encoder")


def test_control_response_authenticator_is_verified():
    from atd_radius.domain.radius_codec import (
        encode_control_request,
        verify_control_response,
    )

    original = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 47, {"User-Name": "alice"}, bytes(16)
    )
    request_wire = encode_control_request(original, "shared")
    request = decode(request_wire, "shared")
    response = RadiusPacket(
        RadiusCode.DISCONNECT_ACK, request.identifier, {}, request.authenticator
    )
    response_wire = encode_response(response, request, "shared")
    assert verify_control_response(response_wire, request, "shared")
    assert not verify_control_response(response_wire, request, "wrong")
    assert not verify_control_response(response_wire, RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 48, {"User-Name": "alice"}, request.authenticator
    ), "shared")


def test_control_response_message_authenticator_is_verified():
    from atd_radius.domain.radius_codec import (
        encode_control_request,
        verify_control_response,
    )

    original = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST,
        49,
        {"User-Name": "alice", "Message-Authenticator": "00" * 16},
        bytes(16),
    )
    request = decode(encode_control_request(original, "shared"), "shared")
    response = RadiusPacket(
        RadiusCode.DISCONNECT_ACK, request.identifier, {}, request.authenticator
    )
    wire = encode_response(response, request, "shared")
    assert verify_control_response(wire, request, "shared")
    tampered = bytearray(wire)
    tampered[-1] ^= 1
    assert not verify_control_response(bytes(tampered), request, "shared")



def _signed_control_request_with_raw_attributes(attributes, message_authenticator_offset):
    import hmac
    from hashlib import md5
    from struct import pack

    secret = b"shared"
    length = 20 + len(attributes)
    header = pack("!BBH", 40, 19, length)
    wire = bytearray(header + bytes(16) + attributes)
    ma_start = 20 + message_authenticator_offset
    wire[ma_start : ma_start + 16] = hmac.new(
        secret, bytes(wire), "md5"
    ).digest()
    wire[4:20] = md5(bytes(wire[:4]) + bytes(16) + bytes(wire[20:]) + secret).digest()
    return bytes(wire)


def test_control_request_rejects_malformed_attribute_after_message_authenticator():
    username = bytes((1, 7)) + b"alice"
    message_authenticator = bytes((80, 18)) + bytes(16)
    malformed_tail = bytes((1, 1))
    attributes = username + message_authenticator + malformed_tail
    wire = _signed_control_request_with_raw_attributes(
        attributes, len(username) + 2
    )
    from atd_radius.domain.radius_codec import verify_control_request

    assert not verify_control_request(wire, "shared")


def test_control_request_rejects_duplicate_message_authenticators():
    username = bytes((1, 7)) + b"alice"
    first_message_authenticator = bytes((80, 18)) + bytes(16)
    second_message_authenticator = bytes((80, 18)) + bytes((0x11,)) * 16
    attributes = username + first_message_authenticator + second_message_authenticator
    wire = _signed_control_request_with_raw_attributes(
        attributes, len(username) + 2
    )
    from atd_radius.domain.radius_codec import verify_control_request

    assert not verify_control_request(wire, "shared")


def test_control_request_ignores_padding_beyond_declared_packet_length():
    from atd_radius.domain.radius_codec import encode_control_request, verify_control_request

    request = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 91, {"User-Name": "alice"}, bytes(16)
    )
    wire = encode_control_request(request, "shared")
    assert verify_control_request(wire, "shared")
    assert verify_control_request(wire + bytes((0,)), "shared")


def test_control_response_ignores_padding_beyond_declared_packet_length():
    from atd_radius.domain.radius_codec import (
        encode_control_request,
        verify_control_response,
    )

    request_packet = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 92, {"User-Name": "alice"}, bytes(16)
    )
    request = decode(encode_control_request(request_packet, "shared"), "shared")
    response = RadiusPacket(
        RadiusCode.DISCONNECT_ACK, request.identifier, {}, request.authenticator
    )
    wire = encode_response(response, request, "shared")
    assert verify_control_response(wire, request, "shared")
    assert verify_control_response(wire + bytes((0,)), request, "shared")


def test_control_request_rejects_packet_shorter_than_declared_length():
    from atd_radius.domain.radius_codec import encode_control_request, verify_control_request

    request = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 93, {"User-Name": "alice"}, bytes(16)
    )
    wire = encode_control_request(request, "shared")
    assert not verify_control_request(wire[:-1], "shared")


def test_control_request_rejects_packet_over_rfc_maximum_length():
    from struct import pack
    from atd_radius.domain.radius_codec import verify_control_request

    wire = pack("!BBH", 40, 94, 4097) + bytes(4093)
    assert not verify_control_request(wire, "shared")


def test_control_response_rejects_packet_shorter_than_declared_length():
    from atd_radius.domain.radius_codec import (
        encode_control_request,
        verify_control_response,
    )

    request_packet = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 95, {"User-Name": "alice"}, bytes(16)
    )
    request = decode(encode_control_request(request_packet, "shared"), "shared")
    response = RadiusPacket(
        RadiusCode.DISCONNECT_ACK, request.identifier, {}, request.authenticator
    )
    wire = encode_response(response, request, "shared")
    assert not verify_control_response(wire[:-1], request, "shared")


def test_control_response_rejects_packet_over_rfc_maximum_length():
    from struct import pack
    from atd_radius.domain.radius_codec import verify_control_response

    request_packet = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 96, {"User-Name": "alice"}, bytes(16)
    )
    from atd_radius.domain.radius_codec import encode_control_request

    request = decode(encode_control_request(request_packet, "shared"), "shared")
    wire = pack("!BBH", 41, request.identifier, 4097) + bytes(4093)
    assert not verify_control_response(wire, request, "shared")


@pytest.mark.parametrize("identifier", [-1, 256, True, 1.5, "7"])
def test_control_request_rejects_invalid_identifier_before_wire_encoding(identifier):
    from atd_radius.domain.radius_codec import RadiusCodecError, encode_control_request

    with pytest.raises((RadiusCodecError, ValueError, TypeError)):
        request = RadiusPacket(
            RadiusCode.DISCONNECT_REQUEST, identifier, {"User-Name": "alice"}, bytes(16)
        )
        encode_control_request(request, "shared")


def test_control_request_encoder_rejects_packet_over_rfc_maximum_length():
    from atd_radius.domain.radius_codec import RadiusCodecError, encode_control_request

    attributes = {f"Attr-{number}": "x" * 253 for number in range(150, 170)}
    request = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 97, attributes, bytes(16)
    )
    with pytest.raises(RadiusCodecError, match="4096"):
        encode_control_request(request, "shared")
