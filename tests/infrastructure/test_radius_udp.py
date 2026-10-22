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


def _access_request_with_eap(*, include_message_authenticator):
    secret = b"shared"
    username = bytes((1, 7)) + b"alice"
    eap_payload = bytes.fromhex("0200000501")
    eap_message = bytes((79, len(eap_payload) + 2)) + eap_payload
    attrs = username + eap_message
    if include_message_authenticator:
        attrs += bytes((80, 18)) + bytes(16)
    header = pack("!BBH", 1, 8, 20 + len(attrs))
    authenticator = bytes.fromhex("00112233445566778899aabbccddeeff")
    wire = header + authenticator + attrs
    if include_message_authenticator:
        message_offset = 20 + len(username) + len(eap_message) + 2
        message_authenticator = hmac.new(
            secret, wire[:message_offset] + bytes(16) + wire[message_offset + 16 :], "md5"
        ).digest()
        wire = wire[:message_offset] + message_authenticator + wire[message_offset + 16 :]
    return wire


def test_udp_server_drops_eap_access_request_without_message_authenticator():
    calls = []

    def handler(packet, peer):
        calls.append(packet)
        return RadiusPacket(RadiusCode.ACCESS_ACCEPT, packet.identifier, {}, packet.authenticator)

    server = RadiusUDPServer(handler, SecretResolver())
    sock = FakeSocket(_access_request_with_eap(include_message_authenticator=False))
    server._socket = sock
    server.serve_once()

    assert calls == []
    assert sock.sent == []


def test_udp_server_accepts_eap_access_request_with_valid_message_authenticator():
    calls = []

    def handler(packet, peer):
        calls.append(packet)
        return RadiusPacket(RadiusCode.ACCESS_ACCEPT, packet.identifier, {}, packet.authenticator)

    server = RadiusUDPServer(handler, SecretResolver())
    sock = FakeSocket(_access_request_with_eap(include_message_authenticator=True))
    server._socket = sock
    server.serve_once()

    assert len(calls) == 1
    assert calls[0].attributes["EAP-Message"] == "0200000501"
    assert len(sock.sent) == 1


def test_udp_server_drops_eap_access_request_with_invalid_message_authenticator():
    calls = []

    def handler(packet, peer):
        calls.append(packet)
        return RadiusPacket(RadiusCode.ACCESS_ACCEPT, packet.identifier, {}, packet.authenticator)

    wire = bytearray(_access_request_with_eap(include_message_authenticator=True))
    wire[-1] ^= 1
    server = RadiusUDPServer(handler, SecretResolver())
    sock = FakeSocket(bytes(wire))
    server._socket = sock
    server.serve_once()

    assert calls == []
    assert sock.sent == []
