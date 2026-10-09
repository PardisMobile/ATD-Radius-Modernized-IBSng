"""Compatibility verification for the password semantics in IBSng A1.24.

A1.24's Password class supports plaintext equality and Unix MD5-crypt ($1$)
hashes, and A1.24 admin password updates write MD5-crypt. This module reproduces
the source format without relying on Python's removed/deprecated crypt module.
Use hash_ibsng_password only when native IBSng password-format compatibility is
required; it is not a general-purpose modern password-storage recommendation.
"""
from __future__ import annotations

import hashlib
import hmac
import re

_MD5_CRYPT_RE = re.compile(r"^\$1\$([^$]{1,8})\$([./0-9A-Za-z]{22})$")


def _md5_crypt(password: str, salt: str) -> str:
    """Return the traditional Unix MD5-crypt representation for UTF-8 bytes."""
    salt = salt.split("$", 1)[0][:8]
    password_bytes = password.encode("utf-8")
    salt_bytes = salt.encode("ascii")

    context = hashlib.md5()
    context.update(password_bytes)
    context.update(b"$1$")
    context.update(salt_bytes)

    alternate = hashlib.md5(password_bytes + salt_bytes + password_bytes).digest()
    remaining = len(password_bytes)
    while remaining > 0:
        context.update(alternate[: min(16, remaining)])
        remaining -= 16
    length = len(password_bytes)
    while length:
        context.update(b"\x00" if length & 1 else password_bytes[:1])
        length >>= 1
    digest = context.digest()

    for i in range(1000):
        round_context = hashlib.md5()
        round_context.update(password_bytes if i & 1 else digest)
        if i % 3:
            round_context.update(salt_bytes)
        if i % 7:
            round_context.update(password_bytes)
        round_context.update(digest if i & 1 else password_bytes)
        digest = round_context.digest()

    alphabet = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    def encode24(b2: int, b1: int, b0: int, count: int) -> str:
        value = (b2 << 16) | (b1 << 8) | b0
        result = []
        for _ in range(count):
            result.append(alphabet[value & 0x3F])
            value >>= 6
        return "".join(result)

    encoded = "".join(
        [
            encode24(digest[0], digest[6], digest[12], 4),
            encode24(digest[1], digest[7], digest[13], 4),
            encode24(digest[2], digest[8], digest[14], 4),
            encode24(digest[3], digest[9], digest[15], 4),
            encode24(digest[4], digest[10], digest[5], 4),
            encode24(0, 0, digest[11], 2),
        ]
    )
    return "$1$" + salt + "$" + encoded


def verify_ibsng_password(candidate: str, stored: str) -> bool:
    """Match A1.24 Password.__eq__ behavior for plaintext and MD5-crypt values.

    The source accepts either side as an MD5-crypt value; when neither side is
    a hash it compares plaintext strings. The database CHAR field is padded,
    so only the stored value is right-trimmed here, matching Admin.__init__.
    """
    stored = stored.rstrip()
    stored_match = _MD5_CRYPT_RE.fullmatch(stored)
    candidate_match = _MD5_CRYPT_RE.fullmatch(candidate)

    if stored_match:
        expected = _md5_crypt(candidate, stored_match.group(1))
        return hmac.compare_digest(expected, stored)
    if candidate_match:
        expected = _md5_crypt(stored, candidate_match.group(1))
        return hmac.compare_digest(expected, candidate)
    return hmac.compare_digest(candidate, stored)



def hash_ibsng_password(password: str) -> str:
    """Create a source-compatible A1.24 MD5-crypt password hash with a random salt.

    A1.24's admin password update path trims the submitted value and rejects
    empty strings or characters outside ASCII letters, digits, underscore and
    hyphen. The API performs that same trim before calling this function.
    """
    import secrets

    if not password or re.search(r"[^A-Za-z0-9_\-]", password):
        raise ValueError("password contains characters not accepted by IBSng A1.24")
    salt_alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    salt = "".join(secrets.choice(salt_alphabet) for _ in range(8))
    return _md5_crypt(password, salt)
