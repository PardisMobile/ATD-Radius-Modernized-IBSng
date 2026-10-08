"""UDP client for outbound RADIUS Disconnect/CoA requests."""
from __future__ import annotations

import socket
from collections.abc import Callable

from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import (
    decode,
    encode_control_request,
    verify_control_response,
)


class RadiusControlUDPClient:
    """Send a control request and accept only an authenticated matching reply."""

    def __init__(
        self,
        *,
        timeout: float = 2.0,
        retries: int = 1,
        socket_factory: Callable[..., object] = socket.socket,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if retries < 1:
            raise ValueError("retries must be at least one")
        self.timeout = timeout
        self.retries = retries
        self.socket_factory = socket_factory

    def send(
        self,
        destination: tuple[str, int],
        request: RadiusPacket,
        secret: str,
    ) -> RadiusPacket:
        if request.code not in {RadiusCode.DISCONNECT_REQUEST, RadiusCode.COA_REQUEST}:
            raise ValueError("expected Disconnect-Request or CoA-Request")
        host, port = destination
        if not host or not 1 <= port <= 65535:
            raise ValueError("invalid RADIUS control destination")
        wire = encode_control_request(request, secret)
        with self.socket_factory(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(self.timeout)
            for _ in range(self.retries):
                udp.sendto(wire, destination)
                while True:
                    try:
                        response_wire, peer = udp.recvfrom(4096)
                    except socket.timeout:
                        break
                    if peer != destination:
                        continue
                    if not verify_control_response(response_wire, request, secret):
                        continue
                    return decode(response_wire, secret)
        raise TimeoutError(
            f"no authenticated RADIUS control response from {host}:{port}"
        )
