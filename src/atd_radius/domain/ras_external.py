"""Side-effect boundaries for source-traced A1.24 RAS integrations.

This module defines transport-independent operation requests only. It does not
invent provider commands, SNMP OIDs, RSH payloads, launcher arguments, or
RADIUS Disconnect-Request wire details. Concrete builders must be backed by
canonical A1.24 source evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class ExternalOperation(str, Enum):
    SNMP = "snmp"
    RSH = "rsh"
    LAUNCHER = "launcher"
    RADIUS_DISCONNECT = "radius_disconnect"
    ASTERISK_MANAGER = "asterisk_manager"
    H323 = "h323"
    SIP = "sip"


@dataclass(frozen=True, slots=True)
class ProviderOperationRequest:
    provider: str
    operation: ExternalOperation
    action: str
    parameters: Mapping[str, object]


class ExternalTransport(Protocol):
    def execute(self, request: ProviderOperationRequest) -> object:
        """Execute one already source-derived provider operation."""


class RecordingExternalTransport:
    """Deterministic fake transport for adapter tests.

    It records requests but never performs network/process side effects.
    """

    def __init__(self) -> None:
        self.requests: list[ProviderOperationRequest] = []

    def execute(self, request: ProviderOperationRequest) -> object:
        self.requests.append(request)
        return None


_DISCONNECT_OPERATIONS = {
    "snmp-or-rsh": (ExternalOperation.SNMP, ExternalOperation.RSH),
    "rsh-interface": (ExternalOperation.RSH,),
    "rsh-port": (ExternalOperation.RSH,),
    "snmp-port": (ExternalOperation.SNMP,),
    "launcher": (ExternalOperation.LAUNCHER,),
    "snmp-interface": (ExternalOperation.SNMP,),
    "provider-port": (ExternalOperation.RADIUS_DISCONNECT,),
    "h323-cause": (ExternalOperation.H323,),
}


def disconnect_operations(strategy: str | None) -> tuple[ExternalOperation, ...]:
    """Return only the externally observed operation families for a strategy.

    This is a source-audit boundary, not an implementation of the operation.
    Unknown strategies intentionally produce no operation rather than guessing.
    """
    return _DISCONNECT_OPERATIONS.get(strategy, ())


def build_disconnect_request(
    provider: str,
    strategy: str | None,
    *,
    action: str = "disconnect",
    parameters: Mapping[str, object] | None = None,
) -> ProviderOperationRequest | None:
    """Build a transport-neutral request when exactly one operation is defined.

    Strategies with multiple alternatives (for example Cisco SNMP-or-RSH) are
    deliberately left to a higher-level source-backed adapter.
    """
    operations = disconnect_operations(strategy)
    if len(operations) != 1:
        return None
    return ProviderOperationRequest(
        provider=provider,
        operation=operations[0],
        action=action,
        parameters=dict(parameters or {}),
    )


def build_provider_disconnect_request(
    provider: str,
    strategy: str | None,
    *,
    source_parameters: Mapping[str, object],
) -> ProviderOperationRequest | None:
    """Build a request from parameters already obtained by a provider adapter.

    Parameter names are intentionally not synthesized here. The caller must
    supply the exact source-derived values (for example port, RAS IP,
    interface index, username, or H323 cause) from its provider adapter.
    """
    return build_disconnect_request(
        provider,
        strategy,
        parameters=source_parameters,
    )

def build_chillispot_disconnect_request(
    *,
    disconnect_ip: str,
    disconnect_port: int,
    username: str,
) -> ProviderOperationRequest:
    """Build the source-derived ChilliSpot disconnect envelope.

    A1.24 sends a RADIUS Disconnect-Request to the configured disconnect
    endpoint and identifies the subscriber with User-Name. Wire encoding and
    transport remain the responsibility of the concrete RADIUS transport.
    """
    if not disconnect_ip.strip():
        raise ValueError("disconnect_ip must not be empty")
    if isinstance(disconnect_port, bool) or not isinstance(disconnect_port, int):
        raise ValueError("disconnect_port must be an integer")
    if not 1 <= disconnect_port <= 65535:
        raise ValueError("disconnect_port must be between 1 and 65535")
    if not username.strip():
        raise ValueError("username must not be empty")
    return ProviderOperationRequest(
        provider="chilli_spot",
        operation=ExternalOperation.RADIUS_DISCONNECT,
        action="disconnect",
        parameters={
            "disconnect_ip": disconnect_ip,
            "disconnect_port": disconnect_port,
            "User-Name": username,
        },
    )

def encode_chillispot_disconnect_datagram(
    *,
    disconnect_ip: str,
    disconnect_port: int,
    username: str,
    identifier: int,
    secret: str,
) -> tuple[tuple[str, int], bytes]:
    """Build the known-source-field ChilliSpot Disconnect-Request datagram.

    The source audit establishes the configured endpoint and User-Name
    selector. No additional provider attributes are inferred here.
    """
    from .radius import RadiusCode, RadiusPacket
    from .radius_codec import encode_control_request

    build_chillispot_disconnect_request(
        disconnect_ip=disconnect_ip,
        disconnect_port=disconnect_port,
        username=username,
    )
    packet = RadiusPacket(
        code=RadiusCode.DISCONNECT_REQUEST,
        identifier=identifier,
        attributes={"User-Name": username},
        authenticator=bytes(16),
    )
    return (
        (disconnect_ip, disconnect_port),
        encode_control_request(packet, secret),
    )
