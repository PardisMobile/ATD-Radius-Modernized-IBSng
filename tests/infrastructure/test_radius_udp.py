from hashlib import md5
import hmac
from struct import pack
from unittest.mock import Mock

import pytest

from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import decode
from atd_radius.infrastructure.radius_udp import RadiusUDPServer


def test_udp_server_rejects_negative_duplicate_cache_age():
    with pytest.raises(ValueError, match="duplicate_cache_max_age"):
        RadiusUDPServer(Mock(), Mock(), duplicate_cache_max_age=-1)


class FakeSocket:
    def __init__(self, data, peer=("192.0.2.1", 45000)):
        self.data = data
        self.peer = peer
        self.sent = []

    def recvfrom(self, size):
        return self.data, self.peer

    def sendto(self, data, peer):
        self.sent.append((data, peer))

    def close(self):
        pass


class SecretResolver:
    def secret_for_ip(self, source_ip):
        return "shared"


def _control_request(code=40):
    secret = b"shared"
    sid = bytes((44, 5)) + b"sid"
    msg = bytes((80, 18)) + bytes(16)
    header = pack("!BBH", code, 7, 20 + len(sid) + len(msg))
    ma = hmac.new(secret, header + bytes(16) + sid + msg, "md5").digest()
    body = sid + bytes((80, 18)) + ma
    auth = md5(header + bytes(16) + body + secret).digest()
    return header + auth + body


def test_udp_control_request_reaches_handler_and_returns_wire_response():
    calls = []

    def handler(packet, peer):
        calls.append((packet, peer))
        return RadiusPacket(RadiusCode.DISCONNECT_ACK, packet.identifier, {}, packet.authenticator)

    server = RadiusUDPServer(handler, SecretResolver())
    sock = FakeSocket(_control_request())
    server._socket = sock
    server.serve_once()

    assert calls[0][0].code is RadiusCode.DISCONNECT_REQUEST
    assert sock.sent[0][1] == ("192.0.2.1", 45000)
    response = decode(sock.sent[0][0], "shared")
    assert response.code is RadiusCode.DISCONNECT_ACK
    assert "Message-Authenticator" in response.attributes


def test_udp_control_request_with_bad_authenticator_is_dropped():
    calls = []

    def handler(packet, peer):
        calls.append(packet)
        return RadiusPacket(RadiusCode.DISCONNECT_ACK, packet.identifier, {}, packet.authenticator)

    wire = bytearray(_control_request())
    wire[-1] ^= 1
    server = RadiusUDPServer(handler, SecretResolver())
    sock = FakeSocket(bytes(wire))
    server._socket = sock
    server.serve_once()

    assert calls == []
    assert sock.sent == []
