from hashlib import md5

from atd_radius.domain.radius_auth import (
    RadiusAuthMethod,
    detect_auth_method,
    validate_mschapv2_response,
    verify_chap,
    verify_mschapv2,
    verify_pap,
)


def test_detects_pap_chap_and_mschapv2():
    assert detect_auth_method({"User-Password": "secret"}) is RadiusAuthMethod.PAP
    assert detect_auth_method({"CHAP-Password": b"x"}) is RadiusAuthMethod.CHAP
    assert detect_auth_method({"MS-CHAP2-Response": b"x"}) is RadiusAuthMethod.MSCHAPV2


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
    response = peer_challenge + b"\x00" * 8 + nt_response + b"\x00"
    assert validate_mschapv2_response(response, auth_challenge)
    assert verify_mschapv2(response, "clientPass", "User", auth_challenge)
    assert not verify_mschapv2(response, "wrongPass", "User", auth_challenge)


def test_mschapv2_shape_rejects_bad_reserved_and_flags():
    challenge = b"x" * 16
    valid = b"x" * 16 + b"\x00" * 8 + b"x" * 24 + b"\x00"
    assert validate_mschapv2_response(valid, challenge)
    assert not validate_mschapv2_response(valid[:16] + b"\x01" + valid[17:], challenge)
    assert not validate_mschapv2_response(valid[:-1] + b"\x01", challenge)
