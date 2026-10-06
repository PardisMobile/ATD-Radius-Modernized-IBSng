"""RADIUS credential-method detection and legacy challenge verification."""
from __future__ import annotations

from enum import StrEnum
from hashlib import md5
from hmac import compare_digest
from typing import Mapping


class RadiusAuthMethod(StrEnum):
    PAP = "pap"
    CHAP = "chap"
    MSCHAPV2 = "mschapv2"
    UNKNOWN = "unknown"


def _octets(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        text = value.strip()
        if len(text) % 2 == 0:
            try:
                return bytes.fromhex(text)
            except ValueError:
                pass
        return text.encode()
    return str(value).encode()


def detect_auth_method(attributes: Mapping[str, object]) -> RadiusAuthMethod:
    if attributes.get("MS-CHAP2-Response") is not None:
        return RadiusAuthMethod.MSCHAPV2
    if attributes.get("CHAP-Password") is not None:
        return RadiusAuthMethod.CHAP
    if attributes.get("User-Password") is not None:
        return RadiusAuthMethod.PAP
    return RadiusAuthMethod.UNKNOWN


def verify_pap(supplied: str, stored: str | None) -> bool:
    return stored is not None and compare_digest(supplied, stored)


def verify_chap(
    chap_password: object,
    stored: str | None,
    challenge: object | None,
    *,
    packet_authenticator: bytes = b"",
) -> bool:
    """Verify RFC 2865 CHAP-Password against a cleartext A1.24 password."""
    if stored is None:
        return False
    response = _octets(chap_password)
    if len(response) != 17:
        return False
    chap_id = response[:1]
    digest = response[1:]
    chap_challenge = _octets(challenge) if challenge is not None else packet_authenticator
    expected = md5(chap_id + stored.encode() + chap_challenge).digest()
    return compare_digest(digest, expected)


def validate_mschapv2_response(
    response: object,
    challenge: object | None,
) -> bool:
    """Validate the wire shape only; cryptographic verification remains separate."""
    raw = _octets(response)
    challenge_octets = _octets(challenge) if challenge is not None else b""
    # RFC 2548 MS-CHAP2-Response: Ident + Flags + Peer-Challenge +
    # Reserved + NT-Response + optional trailing fields as carried by the VSA.
    return len(raw) >= 50 and len(challenge_octets) == 16
