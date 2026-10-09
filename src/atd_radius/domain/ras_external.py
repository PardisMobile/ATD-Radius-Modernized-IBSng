"""Side-effect boundaries for source-traced A1.24 RAS integrations.

This module defines transport-independent operation requests only. It does not
invent provider commands, SNMP OIDs, RSH payloads, launcher arguments, or
RADIUS Disconnect-Request wire details. Concrete builders must be backed by
canonical A1.24 source evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address
from types import MappingProxyType
from typing import Mapping, Protocol


class ExternalOperation(str, Enum):
    SNMP = "snmp"
    RSH = "rsh"
    LAUNCHER = "launcher"
    RADIUS_DISCONNECT = "radius_disconnect"
    ASTERISK_MANAGER = "asterisk_manager"
    H323 = "h323"
    SIP = "sip"


def _freeze_parameter(value: object) -> object:
    """Recursively freeze common containers crossing the provider boundary."""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_parameter(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_parameter(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_parameter(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_parameter(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_freeze_parameter(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class ProviderOperationRequest:
    provider: str
    operation: ExternalOperation
    action: str
    parameters: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("provider must not be empty")
        if not isinstance(self.operation, ExternalOperation):
            raise ValueError("operation must be an ExternalOperation")
        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("action must not be empty")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("parameters must be a mapping")
        object.__setattr__(self, "parameters", _freeze_parameter(dict(self.parameters)))


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
    if not isinstance(disconnect_ip, str) or not disconnect_ip.strip():
        raise ValueError("disconnect_ip must be an IPv4 address")
    try:
        disconnect_ip = str(IPv4Address(disconnect_ip))
    except ValueError as exc:
        raise ValueError("disconnect_ip must be an IPv4 address") from exc
    if isinstance(disconnect_port, bool) or not isinstance(disconnect_port, int):
        raise ValueError("disconnect_port must be an integer")
    if not 1 <= disconnect_port <= 65535:
        raise ValueError("disconnect_port must be between 1 and 65535")
    if not isinstance(username, str) or not username.strip():
        raise ValueError("username must be a non-empty string")
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

def build_chillispot_disconnect_packet(
    *,
    username: str,
    identifier: int,
):
    """Build the minimal ChilliSpot Disconnect-Request from source-known fields."""
    from .radius import RadiusCode, RadiusPacket

    if not isinstance(username, str) or not username.strip():
        raise ValueError("username must be a non-empty string")
    return RadiusPacket(
        code=RadiusCode.DISCONNECT_REQUEST,
        identifier=identifier,
        attributes={"User-Name": username},
        authenticator=bytes(16),
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
    from .radius_codec import encode_control_request

    build_chillispot_disconnect_request(
        disconnect_ip=disconnect_ip,
        disconnect_port=disconnect_port,
        username=username,
    )
    packet = build_chillispot_disconnect_packet(
        username=username,
        identifier=identifier,
    )
    return (
        (disconnect_ip, disconnect_port),
        encode_control_request(packet, secret),
    )
