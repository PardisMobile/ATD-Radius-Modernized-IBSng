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
from atd_radius.application.ras_disconnect import RASDisconnectApplicationService
from atd_radius.domain.ras_external import (
    build_portmaster_disconnect_request,
    build_pppd_disconnect_request,
    build_portslave_disconnect_request,
    build_total_control_disconnect_request,
)


class RASTerminationError(RuntimeError):
    """A configured provider did not confirm the requested session termination."""


class PermanentRASTerminationError(RASTerminationError):
    """The provider action cannot succeed without changing session/configuration."""


class UnsupportedRASTermination(PermanentRASTerminationError):
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
        external_service: RASDisconnectApplicationService | None = None,
    ) -> None:
        self._socket_factory = socket_factory
        self._identifier_factory = identifier_factory
        self._external_service = external_service or RASDisconnectApplicationService()

    @staticmethod
    def _target(ras: RAS, session: SessionState) -> _Target:
        attrs = ras.all_attributes()
        username = str(session.attributes.get("User-Name", "")).strip()
        if not username:
            raise PermanentRASTerminationError("session is missing the source-required User-Name")

        provider = ras.ras_type.strip().lower().replace("-", "_").replace(" ", "_")
        if provider in {"chillispot", "chilli spot", "chilli_spot"}:
            host = str(attrs.get("chilli_spot_disconnect_ip", "192.168.1.65")).strip()
            try:
                port = int(attrs.get("chilli_spot_disconnect_port", 3799))
                timeout = float(attrs.get("chilli_spot_radius_timeout", 5))
            except (TypeError, ValueError) as exc:
                raise PermanentRASTerminationError("invalid ChilliSpot disconnect endpoint configuration") from exc
            if not host or not 1 <= port <= 65535 or timeout <= 0:
                raise RASTerminationError("invalid ChilliSpot disconnect endpoint configuration")
            return _Target(host, port, timeout, {"User-Name": username})

        if provider == "mvts":
            try:
                port = int(attrs.get("mvts_radius_auth_port", 1812))
                timeout = float(attrs.get("mvts_radius_timeout", 5))
            except (TypeError, ValueError) as exc:
                raise PermanentRASTerminationError("invalid MVTS disconnect endpoint configuration") from exc
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

    def _terminate_source_snmp(self, ras: RAS, session: SessionState) -> bool:
        """Execute provider-specific SNMP kill branches traced to A1.24."""
        attrs = ras.all_attributes()
        provider = ras.ras_type.strip().lower().replace("-", "_").replace(" ", "_")
        unique_id = str(session.key.unique_id)
        try:
            if provider == "cisco":
                result = self._external_service.disconnect_cisco(
                    ras_ip=ras.ip, port=unique_id,
                    kill_use_snmp=attrs.get("cisco_kill_use_snmp", 1),
                    wrapper=attrs.get("cisco_rsh_command"),
                    community=str(attrs.get("cisco_snmp_community", "public")),
                    timeout=float(attrs.get("cisco_snmp_timeout", 10)),
                    retries=int(attrs.get("cisco_snmp_retries", 3)),
                    snmp_version=str(attrs.get("cisco_snmp_version", "2c")),
                )
                if result is None:
                    raise PermanentRASTerminationError(f"Cisco source termination does not support port {unique_id!r}")
                return True
            if provider == "portmaster":
                request = build_portmaster_disconnect_request(
                    ras_ip=ras.ip, port=unique_id,
                    community=str(attrs.get("portmaster_snmp_community", "public")),
                    timeout=float(attrs.get("portmaster_snmp_timeout", 10)),
                    retries=int(attrs.get("portmaster_snmp_retries", 3)),
                )
                self._external_service.execute_request(request)
                return True
            if provider in {"total_control", "totalcontrol"}:
                request = build_total_control_disconnect_request(
                    ras_ip=ras.ip, interface_index=unique_id,
                    community=str(attrs.get("tc_snmp_community", "public")),
                    timeout=float(attrs.get("tc_snmp_timeout", 10)),
                    retries=int(attrs.get("tc_snmp_retries", 3)),
                )
                self._external_service.execute_request(request)
                return True

            if provider == "portslave":
                request = build_portslave_disconnect_request(
                    command=str(attrs.get("portslave_kill_port_command", "")),
                    ras_ip=ras.ip,
                    port=unique_id,
                )
                result = self._external_service.execute_request(request)
                if getattr(result, "succeeded", None) is not True:
                    raise PermanentRASTerminationError(
                        "PortSlave source launcher did not confirm successful termination"
                    )
                return True
            if provider == "pppd":
                request = build_pppd_disconnect_request(
                    command=str(attrs.get("pppd_kill_port_command", "")),
                    ras_ip=ras.ip,
                    port=unique_id,
                )
                result = self._external_service.execute_request(request)
                if getattr(result, "succeeded", None) is not True:
                    raise PermanentRASTerminationError(
                        "PPPD source launcher did not confirm successful termination"
                    )
                return True
        except (TypeError, ValueError) as exc:
            raise PermanentRASTerminationError(f"invalid {ras.ras_type} termination configuration or session identity") from exc
        return False

    def terminate(self, ras: RAS, session: SessionState, reason: str) -> None:
        """Execute a source-shaped provider termination and require success."""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("termination reason is required")
        provider = ras.ras_type.strip().lower().replace("-", "_").replace(" ", "_")
        if provider in {"cisco", "portmaster", "total_control", "totalcontrol", "portslave", "pppd"}:
            if self._terminate_source_snmp(ras, session):
                return
            raise UnsupportedRASTermination(f"A1.24 {ras.ras_type!r} termination action is not implemented")
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
