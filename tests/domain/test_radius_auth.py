from hashlib import md5

from atd_radius.domain.radius_auth import (
    RadiusAuthMethod,
    detect_auth_method,
    validate_mschapv2_response,
    verify_chap,
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


def test_mschapv2_shape_requires_50_byte_response_and_16_byte_challenge():
    assert validate_mschapv2_response(b"x" * 50, b"x" * 16)
    assert not validate_mschapv2_response(b"x" * 49, b"x" * 16)
    assert not validate_mschapv2_response(b"x" * 50, b"x" * 8)
