"""Source-traced RAS termination adapters for supported A1.24 providers."""
from __future__ import annotations

import secrets
import socket
from collections.abc import Callable
from dataclasses import dataclass

from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import (
    RadiusCodecError,
    decode,
    encode_control_request,
    verify_control_response,
)
from atd_radius.domain.radius_runtime import SessionState
from atd_radius.domain.ras import RAS


class RASTerminationError(RuntimeError):
    """A configured provider did not confirm the requested session termination."""


class UnsupportedRASTermination(RASTerminationError):
    """The A1.24 provider has no implemented termination adapter in ATD yet."""


@dataclass(frozen=True, slots=True)
class _Target:
    host: str
    port: int
    timeout: float
    attributes: dict[str, str]


class SourceRASDisconnectClient:
    """Execute the A1.24 Disconnect-Request paths for ChilliSpot and MVTS.

    A1.24 uses a configured endpoint and User-Name for ChilliSpot, while MVTS
    sends to the RAS IP/authentication port with User-Name and H323-conf-id.
    Other provider types deliberately fail closed until their SNMP/RSH/launcher/
    telephony action has a separately source-traced implementation.
    """

    def __init__(
        self,
        *,
        socket_factory: Callable[..., object] = socket.socket,
        identifier_factory: Callable[[], int] = lambda: secrets.randbelow(256),
    ) -> None:
        self._socket_factory = socket_factory
        self._identifier_factory = identifier_factory

    @staticmethod
    def _target(ras: RAS, session: SessionState) -> _Target:
        attrs = ras.all_attributes()
        username = str(session.attributes.get("User-Name", "")).strip()
        if not username:
            raise RASTerminationError("session is missing the source-required User-Name")

        provider = ras.ras_type.strip().lower().replace("-", "_").replace(" ", "_")
        if provider in {"chillispot", "chilli spot", "chilli_spot"}:
            host = str(attrs.get("chilli_spot_disconnect_ip", "192.168.1.65")).strip()
            try:
                port = int(attrs.get("chilli_spot_disconnect_port", 3799))
                timeout = float(attrs.get("chilli_spot_radius_timeout", 5))
            except (TypeError, ValueError) as exc:
                raise RASTerminationError("invalid ChilliSpot disconnect endpoint configuration") from exc
            if not host or not 1 <= port <= 65535 or timeout <= 0:
                raise RASTerminationError("invalid ChilliSpot disconnect endpoint configuration")
            return _Target(host, port, timeout, {"User-Name": username})

        if provider == "mvts":
            try:
                port = int(attrs.get("mvts_radius_auth_port", 1812))
                timeout = float(attrs.get("mvts_radius_timeout", 5))
            except (TypeError, ValueError) as exc:
                raise RASTerminationError("invalid MVTS disconnect endpoint configuration") from exc
            if not 1 <= port <= 65535 or timeout <= 0:
                raise RASTerminationError("invalid MVTS disconnect endpoint configuration")
            return _Target(
                ras.ip,
                port,
                timeout,
                {
                    "User-Name": username,
                    "H323-conf-id": f"h323-conf-id={session.key.unique_id}",
                },
            )

        raise UnsupportedRASTermination(
            f"A1.24 {ras.ras_type!r} termination action is not implemented"
        )

    def terminate(self, ras: RAS, session: SessionState, reason: str) -> None:
        """Send a source-shaped Disconnect-Request and require an authenticated ACK."""
        if not reason.strip():
            raise ValueError("termination reason is required")
        target = self._target(ras, session)
        request = RadiusPacket(
            RadiusCode.DISCONNECT_REQUEST,
            self._identifier_factory(),
            target.attributes,
        )
        wire = encode_control_request(request, ras.radius_secret)
        request = RadiusPacket(
            request.code,
            request.identifier,
            request.attributes,
            wire[4:20],
        )

        try:
            expected_host = socket.gethostbyname(target.host)
            with self._socket_factory(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(target.timeout)
                client.sendto(wire, (target.host, target.port))
                response_wire, source = client.recvfrom(4096)
        except (OSError, TimeoutError) as exc:
            raise RASTerminationError(
                f"{ras.ras_type} did not answer the Disconnect-Request"
            ) from exc

        if source[0] != expected_host or source[1] != target.port:
            raise RASTerminationError("Disconnect-Request response came from an unexpected endpoint")
        try:
            response = decode(response_wire, ras.radius_secret)
        except RadiusCodecError as exc:
            raise RASTerminationError("Disconnect-Request response is malformed") from exc

        # A1.24 explicitly disables reply-authenticator verification for MVTS:
        # its implementation notes that MVTS zero-fills the authenticator.
        # Keep endpoint, identifier and response-code checks, but do not apply
        # the normal RFC response-authenticator check to this provider.
        if response.identifier != request.identifier:
            raise RASTerminationError("Disconnect-Request response identifier does not match")
        if ras.ras_type.strip().lower() != "mvts" and not verify_control_response(
            response_wire, request, ras.radius_secret
        ):
            raise RASTerminationError("Disconnect-Request response authenticator is invalid")
        if response.code not in {RadiusCode.DISCONNECT_ACK, RadiusCode.DISCONNECT_NAK}:
            raise RASTerminationError("Disconnect-Request received an unexpected response code")
        if response.code is not RadiusCode.DISCONNECT_ACK:
            cause = response.attributes.get("Error-Cause", "unspecified")
            raise RASTerminationError(f"{ras.ras_type} rejected Disconnect-Request (Error-Cause {cause})")
