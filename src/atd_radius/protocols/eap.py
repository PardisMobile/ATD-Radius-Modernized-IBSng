from dataclasses import dataclass
import hashlib
import hmac


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
