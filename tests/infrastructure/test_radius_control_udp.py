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



@pytest.mark.parametrize(
    ("request_code", "response_code"),
    [
        (RadiusCode.COA_REQUEST, RadiusCode.COA_ACK),
        (RadiusCode.COA_REQUEST, RadiusCode.COA_NAK),
        (RadiusCode.DISCONNECT_REQUEST, RadiusCode.DISCONNECT_NAK),
    ],
)
def test_udp_control_client_supports_coa_and_authenticated_nak(request_code, response_code):
    fake = FakeSocket(response_code=response_code)
    client = RadiusControlUDPClient(socket_factory=lambda *_args: fake)
    request = RadiusPacket(request_code, 73, {"User-Name": "alice"}, bytes(16))
    response = client.send(("192.0.2.20", 1700), request, "shared")
    assert response.code is response_code
    assert response.identifier == 73


def test_udp_control_client_ignores_packet_from_unconfigured_peer():
    class SpoofedPeerSocket(FakeSocket):
        def recvfrom(self, size):
            wire, _peer = super().recvfrom(size)
            return wire, ("192.0.2.99", 1700)

    fake = SpoofedPeerSocket()
    client = RadiusControlUDPClient(
        timeout=0.01,
        retries=1,
        socket_factory=lambda *_args: fake,
    )
    request = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 74, {"User-Name": "alice"}, bytes(16)
    )
    with pytest.raises(TimeoutError):
        client.send(("192.0.2.20", 1700), request, "shared")


def test_udp_control_client_retries_after_timeout():
    class DropFirstReplySocket(FakeSocket):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def sendto(self, wire, destination):
            self.calls += 1
            if self.calls == 1:
                self.sent.append((wire, destination))
                return
            super().sendto(wire, destination)

    fake = DropFirstReplySocket()
    client = RadiusControlUDPClient(
        timeout=0.01,
        retries=2,
        socket_factory=lambda *_args: fake,
    )
    request = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 75, {"User-Name": "alice"}, bytes(16)
    )
    response = client.send(("192.0.2.20", 1700), request, "shared")
    assert response.code is RadiusCode.DISCONNECT_ACK
    assert fake.calls == 2


@pytest.mark.parametrize(
    ("timeout", "retries"),
    [(0, 1), (-1, 1), (1, 0), (1, -1)],
)
def test_udp_control_client_rejects_invalid_timeout_and_retry_bounds(timeout, retries):
    with pytest.raises(ValueError):
        RadiusControlUDPClient(timeout=timeout, retries=retries)


@pytest.mark.parametrize("destination", [
    ("", 1700),
    ("radius.example.test", 1700),
    ("2001:db8::1", 1700),
    ("192.0.2.20", 0),
    ("192.0.2.20", True),
    ("192.0.2.20", 65536),
])
def test_udp_control_client_rejects_invalid_destination_before_socket_creation(destination):
    client = RadiusControlUDPClient(
        socket_factory=lambda *_args: (_ for _ in ()).throw(
            AssertionError("socket must not be created for an invalid destination")
        )
    )
    request = RadiusPacket(
        RadiusCode.DISCONNECT_REQUEST, 76, {"User-Name": "alice"}, bytes(16)
    )
    with pytest.raises(ValueError):
        client.send(destination, request, "shared")


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), float("-inf"), True])
def test_udp_control_client_rejects_non_finite_or_boolean_timeout(timeout):
    with pytest.raises(ValueError):
        RadiusControlUDPClient(timeout=timeout)


@pytest.mark.parametrize("retries", [True, 1.5, "2"])
def test_udp_control_client_rejects_non_integer_retry_count(retries):
    with pytest.raises(ValueError):
        RadiusControlUDPClient(retries=retries)
