from hashlib import md5, sha1

from atd_radius.domain.radius_auth import (
    RadiusAuthMethod,
    detect_auth_method,
    validate_mschapv2_response,
    verify_mschapv1,
    derive_mschapv1_mppe_key,
    verify_chap,
    verify_mschapv2,
    generate_mschapv2_authenticator_response,
    derive_mschapv2_mppe_keys,
    verify_pap,
)


def test_detects_pap_chap_and_mschapv2():
    assert detect_auth_method({"User-Password": "secret"}) is RadiusAuthMethod.PAP
    assert detect_auth_method({"CHAP-Password": b"x"}) is RadiusAuthMethod.CHAP
    assert detect_auth_method({"MS-CHAP2-Response": b"x"}) is RadiusAuthMethod.MSCHAPV2
    assert detect_auth_method({"MS-CHAP-Response": b"x"}) is RadiusAuthMethod.MSCHAPV1


def test_chap_verification_uses_identifier_password_and_challenge():
    identifier = b"\x01"
    challenge = b"challenge"
    digest = md5(identifier + b"secret" + challenge).digest()
    assert verify_chap(identifier + digest, "secret", challenge)
    assert not verify_chap(identifier + digest, "wrong", challenge)


def test_chap_can_use_packet_authenticator_when_challenge_attribute_is_absent():
    authenticator = bytes(range(16))
    identifier = b"\x07"
    digest = md5(identifier + b"secret" + authenticator).digest()
    assert verify_chap(identifier + digest, "secret", None, packet_authenticator=authenticator)


def test_pap_verification_is_constant_time_and_exact():
    assert verify_pap("secret", "secret")
    assert not verify_pap("secret", "Secret")


def test_mschapv2_rfc2759_vector():
    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    response = b"\x01\x00" + peer_challenge + b"\x00" * 8 + nt_response
    assert validate_mschapv2_response(response, auth_challenge)
    assert verify_mschapv2(response, "clientPass", "User", auth_challenge)
    assert not verify_mschapv2(response, "wrongPass", "User", auth_challenge)


def test_mschapv1_verification_matches_a124_nt_response():
    challenge = bytes.fromhex("5B5D7C7D7B3F2F3E")
    nt_response = bytes.fromhex("9F9BEC2D4EA5BD51E59EC761C102526860A6C4DE36AFB512")
    response = b"\x01\x00" + b"\x00" * 16 + b"\x00" * 8 + nt_response
    assert verify_mschapv1(response, "clientPass", challenge)
    assert not verify_mschapv1(response, "wrongPass", challenge)
    assert len(derive_mschapv1_mppe_key("clientPass")) == 32


def test_mschapv2_shape_matches_a124_field_consumption():
    challenge = b"x" * 16
    valid = b"\x01\x00" + b"x" * 16 + b"\x00" * 8 + b"x" * 24
    assert validate_mschapv2_response(valid, challenge)
    assert validate_mschapv2_response(valid[:18] + b"\x01" + valid[19:], challenge)
    assert validate_mschapv2_response(valid[:1] + b"\x01" + valid[2:], challenge)


def test_mschapv2_rfc2759_authenticator_response():
    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    assert generate_mschapv2_authenticator_response(
        "clientPass",
        nt_response,
        peer_challenge,
        auth_challenge,
        "User",
    ) == "S=407A5589115FD0D6209F510FE9C04566932CDA56"


def test_mschapv2_mppe_server_keys_are_rfc3079_derived():
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    send_key, recv_key = derive_mschapv2_mppe_keys("clientPass", nt_response)
    assert send_key.hex() == "8b7cdc149b993a1ba118cb153f56dccb"
    assert recv_key.hex() == "d5f0e9521e3ea9589645e86051c82226"



def test_a124_str2unicode_interleaves_utf8_source_bytes_not_unicode_codepoints():
    from atd_radius.domain.radius_auth import _a124_str2unicode

    assert _a124_str2unicode("clientPass") == "clientPass".encode("utf-16le")
    assert _a124_str2unicode("é") == b"\xc3\x00\xa9\x00"


def test_mschapv2_rfc2759_vector_remains_valid_after_source_password_conversion():
    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    response = b"\x01\x00" + peer_challenge + b"\x00" * 8 + nt_response
    assert verify_mschapv2(response, "clientPass", "User", auth_challenge)


def test_a124_non_ascii_mschapv2_pipeline_uses_one_source_password_hash():
    from hashlib import sha1
    from atd_radius.domain.radius_auth import (
        _a124_str2unicode,
        _challenge_hash,
        _md4,
        _nt_response,
    )

    password = "päss-é"
    username = "normalized-user"
    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    challenge = _challenge_hash(peer_challenge, auth_challenge, username)
    nt_response = _nt_response(challenge, password)
    response = b"\x01\x00" + peer_challenge + b"\x00" * 8 + nt_response

    # The complete non-ASCII response must verify against A1.24's byte-wise
    # password conversion, not Python's Unicode-code-point UTF-16LE encoding.
    assert _a124_str2unicode(password) != password.encode("utf-16le")
    assert verify_mschapv2(response, password, username, auth_challenge)

    password_hash_hash = _md4(_md4(_a124_str2unicode(password)))
    digest = sha1(
        password_hash_hash + nt_response + b"Magic server to client signing constant"
    ).digest()
    digest = sha1(
        digest + challenge + b"Pad to make it do more than one iteration"
    ).digest()
    expected_authenticator_response = "S=" + digest.hex().upper()
    assert generate_mschapv2_authenticator_response(
        password, nt_response, peer_challenge, auth_challenge, username
    ) == expected_authenticator_response

    master_key = sha1(
        password_hash_hash + nt_response + b"This is the MPPE Master Key"
    ).digest()[:16]
    pad1 = b"\x00" * 40
    pad2 = b"\xf2" * 40
    expected_send = sha1(
        master_key + pad1
        + b"On the client side, this is the receive key; on the server side, it is the send key."
        + pad2
    ).digest()[:16]
    expected_recv = sha1(
        master_key + pad1
        + b"On the client side, this is the send key; on the server side, it is the receive key."
        + pad2
    ).digest()[:16]
    assert derive_mschapv2_mppe_keys(password, nt_response) == (expected_send, expected_recv)


def test_mschapv2_authenticator_response_uses_a124_bytewise_password_conversion():
    from atd_radius.domain.radius_auth import _a124_str2unicode, _md4

    password = "é"
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    password_hash_hash = _md4(_md4(_a124_str2unicode(password)))
    magic1 = b"Magic server to client signing constant"
    digest = sha1(password_hash_hash + nt_response + magic1).digest()
    challenge = sha1(peer_challenge + auth_challenge + b"User").digest()[:8]
    magic2 = b"Pad to make it do more than one iteration"
    expected = "S=" + sha1(digest + challenge + magic2).hexdigest().upper()
    assert generate_mschapv2_authenticator_response(
        password, nt_response, peer_challenge, auth_challenge, "User"
    ) == expected
