import socket

import pytest

from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import decode, encode_response
from atd_radius.infrastructure.radius_control_udp import RadiusControlUDPClient


class FakeSocket:
    def __init__(self, secret="shared", response_code=RadiusCode.DISCONNECT_ACK):
        self.secret = secret
        self.response_code = response_code
        self.timeout = None
        self.pending = []
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, value):
        self.timeout = value

    def sendto(self, wire, destination):
        self.sent.append((wire, destination))
        request = decode(wire, self.secret)
        response = RadiusPacket(
            self.response_code,
            request.identifier,
            {},
            request.authenticator,
        )
        self.pending.append((encode_response(response, request, self.secret), destination))

    def recvfrom(self, _size):
        if not self.pending:
            raise socket.timeout()
        return self.pending.pop(0)


def test_udp_control_client_sends_and_verifies_disconnect_ack():
    fake = FakeSocket()
    client = RadiusControlUDPClient(
        timeout=0.25,
        retries=2,
        socket_factory=lambda *_args: fake,
    )
    request = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 53, {"User-Name": "alice"}, bytes(16)
    )
    response = client.send(("192.0.2.20", 1700), request, "shared")
    assert response.code is RadiusCode.DISCONNECT_ACK
    assert response.identifier == 53
    assert fake.timeout == 0.25
    assert len(fake.sent) == 1
    assert fake.sent[0][1] == ("192.0.2.20", 1700)


def test_udp_control_client_rejects_wrong_response_identifier_until_timeout():
    class WrongIdentifierSocket(FakeSocket):
        def sendto(self, wire, destination):
            request = decode(wire, self.secret)
            response = RadiusPacket(
                RadiusCode.DISCONNECT_ACK,
                (request.identifier + 1) % 256,
                {},
                request.authenticator,
            )
            self.pending.append((encode_response(response, request, self.secret), destination))

    fake = WrongIdentifierSocket()
    client = RadiusControlUDPClient(
        timeout=0.01,
        retries=1,
        socket_factory=lambda *_args: fake,
    )
    request = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 54, {"User-Name": "alice"}, bytes(16)
    )
    with pytest.raises(TimeoutError):
        client.send(("192.0.2.20", 1700), request, "shared")


def test_udp_control_client_rejects_access_request():
    client = RadiusControlUDPClient(socket_factory=lambda *_args: None)
    request = RadiusPacket(
        RadiusCode.ACCESS_REQUEST, 55, {"User-Name": "alice"}, bytes(16)
    )
    with pytest.raises(ValueError):
        client.send(("192.0.2.20", 1700), request, "shared")
