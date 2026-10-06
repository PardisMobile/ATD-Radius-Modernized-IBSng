"""RADIUS credential-method detection and challenge-response verification."""
from __future__ import annotations

from enum import StrEnum
from hashlib import md5, sha1
from hmac import compare_digest
from typing import Mapping

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


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


def _md4(data: bytes) -> bytes:
    """Minimal RFC-compatible MD4 implementation for NT password hashes."""
    message = bytearray(data)
    bit_length = len(message) * 8
    message.append(0x80)
    while len(message) % 64 != 56:
        message.append(0)
    message.extend(bit_length.to_bytes(8, "little"))
    a0, b0, c0, d0 = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476

    def rol(value: int, shift: int) -> int:
        return ((value << shift) | (value >> (32 - shift))) & 0xFFFFFFFF

    for offset in range(0, len(message), 64):
        x = [int.from_bytes(message[offset + i : offset + i + 4], "little") for i in range(0, 64, 4)]
        a, b, c, d = a0, b0, c0, d0

        def f(xv: int, y: int, z: int) -> int:
            return (xv & y) | (~xv & z)

        def g(xv: int, y: int, z: int) -> int:
            return (xv & y) | (xv & z) | (y & z)

        for i, shift in zip(range(16), [3, 7, 11, 19] * 4):
            k = i
            if i % 4 == 0:
                a = rol((a + f(b, c, d) + x[k]) & 0xFFFFFFFF, shift)
            elif i % 4 == 1:
                d = rol((d + f(a, b, c) + x[k]) & 0xFFFFFFFF, shift)
            elif i % 4 == 2:
                c = rol((c + f(d, a, b) + x[k]) & 0xFFFFFFFF, shift)
            else:
                b = rol((b + f(c, d, a) + x[k]) & 0xFFFFFFFF, shift)

        order = [0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15]
        for i, shift in zip(range(16), [3, 5, 9, 13] * 4):
            k = order[i]
            if i % 4 == 0:
                a = rol((a + g(b, c, d) + x[k] + 0x5A827999) & 0xFFFFFFFF, shift)
            elif i % 4 == 1:
                d = rol((d + g(a, b, c) + x[k] + 0x5A827999) & 0xFFFFFFFF, shift)
            elif i % 4 == 2:
                c = rol((c + g(d, a, b) + x[k] + 0x5A827999) & 0xFFFFFFFF, shift)
            else:
                b = rol((b + g(c, d, a) + x[k] + 0x5A827999) & 0xFFFFFFFF, shift)

        order = [0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15]
        for i, shift in zip(range(16), [3, 9, 11, 15] * 4):
            k = order[i]
            if i % 4 == 0:
                a = rol((a + (b ^ c ^ d) + x[k] + 0x6ED9EBA1) & 0xFFFFFFFF, shift)
            elif i % 4 == 1:
                d = rol((d + (a ^ b ^ c) + x[k] + 0x6ED9EBA1) & 0xFFFFFFFF, shift)
            elif i % 4 == 2:
                c = rol((c + (d ^ a ^ b) + x[k] + 0x6ED9EBA1) & 0xFFFFFFFF, shift)
            else:
                b = rol((b + (c ^ d ^ a) + x[k] + 0x6ED9EBA1) & 0xFFFFFFFF, shift)

        a0 = (a0 + a) & 0xFFFFFFFF
        b0 = (b0 + b) & 0xFFFFFFFF
        c0 = (c0 + c) & 0xFFFFFFFF
        d0 = (d0 + d) & 0xFFFFFFFF
    return b"".join(value.to_bytes(4, "little") for value in (a0, b0, c0, d0))


def _des_key(key7: bytes) -> bytes:
    if len(key7) != 7:
        raise ValueError("MS-CHAPv2 DES key fragment must be 7 bytes")
    key = bytearray(8)
    key[0] = key7[0] & 0xFE
    key[1] = ((key7[0] << 7) | (key7[1] >> 1)) & 0xFE
    key[2] = ((key7[1] << 6) | (key7[2] >> 2)) & 0xFE
    key[3] = ((key7[2] << 5) | (key7[3] >> 3)) & 0xFE
    key[4] = ((key7[3] << 4) | (key7[4] >> 4)) & 0xFE
    key[5] = ((key7[4] << 3) | (key7[5] >> 5)) & 0xFE
    key[6] = ((key7[5] << 2) | (key7[6] >> 6)) & 0xFE
    key[7] = (key7[6] << 1) & 0xFE
    for i in range(8):
        key[i] |= 1 if key[i].bit_count() % 2 == 0 else 0
    return bytes(key)


def _des_encrypt(clear: bytes, key7: bytes) -> bytes:
    key = _des_key(key7)
    cipher = Cipher(algorithms.TripleDES(key * 3), modes.ECB())
    return cipher.encryptor().update(clear)


def _challenge_hash(peer: bytes, authenticator: bytes, username: str) -> bytes:
    if len(peer) != 16 or len(authenticator) != 16:
        raise ValueError("MS-CHAPv2 challenges must be 16 bytes")
    name = username.split("\\", 1)[-1].encode()
    return sha1(peer + authenticator + name).digest()[:8]


def _nt_response(challenge: bytes, password: str) -> bytes:
    password_hash = _md4(password.encode("utf-16le"))
    zpwd = password_hash + b"\x00" * 5
    return b"".join(_des_encrypt(challenge, zpwd[i : i + 7]) for i in (0, 7, 14))


def verify_mschapv2(
    response: object,
    stored: str | None,
    username: str,
    challenge: object,
) -> bool:
    """Verify the RFC 2548 MS-CHAP2-Response VSA value."""
    if stored is None:
        return False
    raw = _octets(response)
    auth_challenge = _octets(challenge)
    if len(raw) != 50 or len(auth_challenge) != 16:
        return False

    # RFC 2548 VSA value: Ident, Flags, Peer-Challenge, Reserved, NT-Response.
    peer_challenge = raw[2:18]
    reserved = raw[18:26]
    nt_response = raw[26:50]
    flags = raw[1]
    if reserved != b"\x00" * 8 or flags != 0:
        return False

    challenge_hash = _challenge_hash(peer_challenge, auth_challenge, username)
    expected = _nt_response(challenge_hash, stored)
    return compare_digest(nt_response, expected)



def generate_mschapv2_authenticator_response(
    password: str,
    nt_response: object,
    peer_challenge: object,
    authenticator_challenge: object,
    username: str,
) -> str:
    """Generate the RFC 2759 MS-CHAPv2 AuthenticatorResponse (S=...)."""
    nt = _octets(nt_response)
    peer = _octets(peer_challenge)
    auth = _octets(authenticator_challenge)
    if len(nt) != 24 or len(peer) != 16 or len(auth) != 16:
        raise ValueError("invalid MS-CHAPv2 response/challenge length")
    password_hash = _md4(password.encode("utf-16le"))
    password_hash_hash = _md4(password_hash)
    magic1 = b"Magic server to client signing constant"
    digest = sha1(password_hash_hash + nt + magic1).digest()
    challenge = _challenge_hash(peer, auth, username)
    magic2 = b"Pad to make it do more than one iteration"
    digest = sha1(digest + challenge + magic2).digest()
    return "S=" + digest.hex().upper()

def validate_mschapv2_response(response: object, challenge: object | None) -> bool:
    """Validate the RFC 2548 MS-CHAP2-Response VSA shape."""
    raw = _octets(response)
    challenge_octets = _octets(challenge) if challenge is not None else b""
    return (
        len(raw) == 50
        and len(challenge_octets) == 16
        and raw[18:26] == b"\x00" * 8
        and raw[1] == 0
    )
