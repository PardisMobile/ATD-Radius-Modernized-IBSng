import socket

from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import decode, encode_response
from atd_radius.infrastructure.chillispot_disconnect import ChilliSpotDisconnectClient
from atd_radius.infrastructure.radius_control_udp import RadiusControlUDPClient


class FakeSocket:
    def __init__(self, response_code=RadiusCode.DISCONNECT_ACK, secret="shared"):
        self.response_code = response_code
        self.secret = secret
        self.pending = []
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, _timeout):
        pass

    def sendto(self, wire, destination):
        self.sent.append((wire, destination))
        request = decode(wire, self.secret)
        response = RadiusPacket(
            self.response_code, request.identifier, {}, request.authenticator
        )
        self.pending.append((encode_response(response, request, self.secret), destination))

    def recvfrom(self, _size):
        if not self.pending:
            raise socket.timeout()
        return self.pending.pop(0)


def test_chillispot_disconnect_executes_source_scoped_authenticated_request():
    fake = FakeSocket()
    control = RadiusControlUDPClient(socket_factory=lambda *_args: fake)
    client = ChilliSpotDisconnectClient(control)
    response = client.disconnect(
        disconnect_ip="192.0.2.20",
        disconnect_port=1700,
        username="alice",
        identifier=61,
        secret="shared",
    )
    sent_wire, destination = fake.sent[0]
    sent_packet = decode(sent_wire, "shared")
    assert destination == ("192.0.2.20", 1700)
    assert sent_packet.code is RadiusCode.DISCONNECT_REQUEST
    assert sent_packet.attributes == {"User-Name": "alice"}
    assert response.code is RadiusCode.DISCONNECT_ACK
    assert response.identifier == 61


def test_chillispot_disconnect_preserves_authenticated_nak_for_caller():
    fake = FakeSocket(response_code=RadiusCode.DISCONNECT_NAK)
    client = ChilliSpotDisconnectClient(
        RadiusControlUDPClient(socket_factory=lambda *_args: fake)
    )
    response = client.disconnect(
        disconnect_ip="192.0.2.20",
        disconnect_port=1700,
        username="alice",
        identifier=62,
        secret="shared",
    )
    assert response.code is RadiusCode.DISCONNECT_NAK
