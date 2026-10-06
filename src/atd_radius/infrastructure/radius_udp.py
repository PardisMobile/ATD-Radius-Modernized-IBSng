"""UDP transport for the RADIUS domain dispatcher."""
from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Protocol

from .radius import RadiusCode, RadiusPacket
from .radius_codec import decode, encode, encode_response


class RadiusSecretResolver(Protocol):
    def secret_for_ip(self, source_ip: str) -> str | None: ...


class RadiusUDPServer:
    """Small synchronous UDP server; production lifecycle owns threading/process policy."""

    def __init__(
        self,
        handler: Callable[[RadiusPacket, tuple[str, int]], RadiusPacket],
        secret_resolver: RadiusSecretResolver,
        host: str = "0.0.0.0",
        port: int = 1812,
        max_packet_size: int = 4096,
    ) -> None:
        self.handler = handler
        self.secret_resolver = secret_resolver
        self.host = host
        self.port = port
        self.max_packet_size = max_packet_size
        self._socket: socket.socket | None = None

    def serve_once(self) -> None:
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.bind((self.host, self.port))
        data, peer = self._socket.recvfrom(self.max_packet_size)
        secret = self.secret_resolver.secret_for_ip(peer[0])
        if not secret:
            return
        request = decode(data, secret)
        response = self.handler(request, peer)
        if request.code is RadiusCode.ACCESS_REQUEST and response.code in {
            RadiusCode.ACCESS_ACCEPT, RadiusCode.ACCESS_REJECT, RadiusCode.ACCESS_CHALLENGE,
        }:
            wire = encode_response(response, request, secret)
        elif request.code is RadiusCode.ACCOUNTING_REQUEST and response.code is RadiusCode.ACCOUNTING_RESPONSE:
            wire = encode_response(response, request, secret)
        else:
            wire = encode(response, secret)
        self._socket.sendto(wire, peer)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
