from dataclasses import dataclass
import hashlib
import hmac
import struct


@dataclass(frozen=True, slots=True)
class RadiusPacket:
    code: int
    identifier: int
    authenticator: bytes
    attributes: bytes

    def encode(self) -> bytes:
        body = self.attributes
        length = 20 + len(body)
        if len(self.authenticator) != 16:
            raise ValueError("RADIUS authenticator must be 16 bytes")
        return struct.pack("!BBH", self.code, self.identifier, length) + self.authenticator + body

    @classmethod
    def decode(cls, packet: bytes) -> "RadiusPacket":
        if len(packet) < 20:
            raise ValueError("RADIUS packet is shorter than 20 bytes")
        code, identifier, length = struct.unpack("!BBH", packet[:4])
        if length < 20 or length > len(packet):
            raise ValueError("invalid RADIUS length")
        return cls(code, identifier, packet[4:20], packet[20:length])


def verify_request_authenticator(packet: bytes, secret: bytes) -> bool:
    if len(packet) < 20:
        return False
    declared = packet[4:20]
    candidate = hashlib.md5(packet[:4] + (b"\x00" * 16) + packet[20:] + secret).digest()
    return hmac.compare_digest(declared, candidate)
