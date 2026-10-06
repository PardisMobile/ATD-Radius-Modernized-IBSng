"""UDP transport for the RADIUS domain dispatcher."""
from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Protocol

from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import decode, encode_response, verify_accounting_request
from atd_radius.domain.radius_runtime import DuplicateRequestCache, RequestKey


class RadiusSecretResolver(Protocol):
    def secret_for_ip(self, source_ip: str) -> str | None: ...


class RadiusUDPServer:
    """Synchronous UDP transport with NAS secret lookup and duplicate replay."""

    def __init__(
        self,
        handler: Callable[[RadiusPacket, tuple[str, int]], RadiusPacket],
        secret_resolver: RadiusSecretResolver,
        host: str = "0.0.0.0",
        port: int = 1812,
        max_packet_size: int = 4096,
        duplicate_cache: DuplicateRequestCache[bytes] | None = None,
        duplicate_cache_max_age: float = 300.0,
    ) -> None:
        self.handler = handler
        self.secret_resolver = secret_resolver
        self.host = host
        self.port = port
        self.max_packet_size = max_packet_size
        if duplicate_cache_max_age < 0:
            raise ValueError("duplicate_cache_max_age must be non-negative")
        self.cache = duplicate_cache or DuplicateRequestCache()
        self.duplicate_cache_max_age = duplicate_cache_max_age
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
        if request.code is RadiusCode.ACCOUNTING_REQUEST and not verify_accounting_request(data, secret):
            return
        self.cache.purge_expired(self.duplicate_cache_max_age)
        key = RequestKey(peer[0], peer[1], request.identifier, int(data[0]), request.authenticator)
        cached = self.cache.get(key)
        if cached is not None:
            if cached.response is not None:
                self._socket.sendto(cached.response, peer)
            return
        self.cache.add(key)
        try:
            response = self.handler(request, peer)
            wire = encode_response(response, request, secret)
            self.cache.finish(key, wire)
            self._socket.sendto(wire, peer)
        except Exception:
            self.cache.remove(key)
            raise

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
