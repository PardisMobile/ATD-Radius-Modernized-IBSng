"""RADIUS EAP-Message primitives.

IBSng A1.24 has no EAP implementation. EAP is an ATD extension. Transport
and EAP method state machines must remain separate from these packet helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac

EAP_MESSAGE_ATTRIBUTE = 79
MESSAGE_AUTHENTICATOR_ATTRIBUTE = 80


@dataclass(frozen=True, slots=True)
class EAPPacket:
    code: int
    identifier: int
    data: bytes

    @property
    def length(self) -> int:
        return 4 + len(self.data)

    def encode(self) -> bytes:
        length = self.length
        if length > 0xFFFF:
            raise ValueError("EAP packet is too large")
        return bytes((self.code, self.identifier)) + length.to_bytes(2, "big") + self.data

    @classmethod
    def decode(cls, packet: bytes) -> "EAPPacket":
        if len(packet) < 4:
            raise ValueError("EAP packet is shorter than the four-byte header")
        length = int.from_bytes(packet[2:4], "big")
        if length < 4 or length > len(packet):
            raise ValueError("invalid EAP length")
        return cls(packet[0], packet[1], packet[4:length])


def message_authenticator(secret: bytes, packet_without_attribute: bytes) -> bytes:
    return hmac.new(secret, packet_without_attribute, hashlib.md5).digest()


def join_eap_message(attributes: list[bytes]) -> bytes:
    return b"".join(attributes)


def split_eap_message(packet: bytes, chunk_size: int = 253) -> list[bytes]:
    if not 1 <= chunk_size <= 253:
        raise ValueError("chunk_size must be between 1 and 253")
    return [packet[i:i + chunk_size] for i in range(0, len(packet), chunk_size)]
