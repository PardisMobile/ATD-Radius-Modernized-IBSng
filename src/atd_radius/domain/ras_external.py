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
