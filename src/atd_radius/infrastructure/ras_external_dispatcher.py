"""Dispatch audited RAS operation envelopes to concrete bounded transports.

This is an explicit infrastructure boundary, not an automatic accounting hook:
callers must first select a source-derived provider branch and build its request.
RSH remains intentionally unsupported until a safe, source-compatible wrapper
transport is implemented and tested.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from atd_radius.domain.ras_external import ExternalOperation, ProviderOperationRequest
from atd_radius.infrastructure.chillispot_disconnect import ChilliSpotDisconnectClient
from atd_radius.infrastructure.launcher_transport import ConfiguredLauncherTransport
from atd_radius.infrastructure.snmp_transport import SnmpV1V2cSetTransport


class _SnmpTransport(Protocol):
    def execute(self, request: ProviderOperationRequest) -> object: ...
    def walk_text_mapping(self, request: ProviderOperationRequest) -> dict[str, str]: ...


class _LauncherTransport(Protocol):
    def execute(self, request: ProviderOperationRequest) -> object: ...


class _ChilliSpotClient(Protocol):
    def disconnect(
        self, *, disconnect_ip: str, disconnect_port: int, username: str,
        identifier: int, secret: str
    ) -> object: ...


class UnsupportedExternalOperation(RuntimeError):
    """No concrete transport is enabled for this audited operation family."""


@dataclass(slots=True)
class RASExternalOperationDispatcher:
    """Dispatch only operations with concrete, bounded transports.

    Dependencies can be injected for tests. No transport is constructed from
    arbitrary user input and this class never falls back to shell execution.
    """

    snmp: _SnmpTransport | None = None
    launcher: _LauncherTransport | None = None
    chillispot: _ChilliSpotClient | None = None

    def __post_init__(self) -> None:
        if self.snmp is None:
            self.snmp = SnmpV1V2cSetTransport()
        if self.launcher is None:
            self.launcher = ConfiguredLauncherTransport()
        if self.chillispot is None:
            self.chillispot = ChilliSpotDisconnectClient()

    @staticmethod
    def _validate_snmp_envelope(request: ProviderOperationRequest) -> None:
        """Restrict dispatch to the provider/OID combinations audited from A1.24."""
        params = request.parameters
        if request.action == "walk":
            if request.provider != "cisco" or params.get("walk_oid") != ".1.3.6.1.2.1.2.2.1.2":
                raise UnsupportedExternalOperation("only the audited Cisco ifDescr walk is enabled")
            return
        if request.action != "disconnect":
            raise UnsupportedExternalOperation(f"unsupported SNMP action: {request.action}")

        allowed_cisco_oid = ".1.3.6.1.4.1.9.2.1.76.0"
        if request.provider == "cisco":
            set_value = params.get("set")
            if not isinstance(set_value, dict) and not hasattr(set_value, "get"):
                raise UnsupportedExternalOperation("Cisco disconnect requires its audited SET envelope")
            if set_value.get("oid") != allowed_cisco_oid:
                raise UnsupportedExternalOperation("Cisco disconnect OID is not source-audited")
            return

        if request.provider not in {"portmaster", "total_control"}:
            raise UnsupportedExternalOperation(f"SNMP provider is not enabled: {request.provider}")
        oid_prefix = ".1.3.6.1.2.1.2.2.1.7."
        sets = params.get("sets") if request.provider == "total_control" else (params.get("set"),)
        if not isinstance(sets, (tuple, list)) or not sets:
            raise UnsupportedExternalOperation("SNMP disconnect requires a source-audited SET sequence")
        for set_value in sets:
            if not hasattr(set_value, "get"):
                raise UnsupportedExternalOperation("invalid SNMP SET envelope")
            oid = set_value.get("oid")
            if not isinstance(oid, str) or not oid.startswith(oid_prefix) or not oid[len(oid_prefix):].isdecimal():
                raise UnsupportedExternalOperation("IF-MIB ifAdminStatus OID is not source-audited")

    def execute(
        self,
        request: ProviderOperationRequest,
        *,
        radius_identifier: int | None = None,
        radius_secret: str | None = None,
    ) -> object:
        if not isinstance(request, ProviderOperationRequest):
            raise ValueError("request must be a ProviderOperationRequest")

        if request.operation is ExternalOperation.SNMP:
            if self.snmp is None:
                raise UnsupportedExternalOperation("SNMP transport is not configured")
            self._validate_snmp_envelope(request)
            if request.action == "walk":
                return self.snmp.walk_text_mapping(request)
            if request.action == "disconnect":
                return self.snmp.execute(request)
            raise UnsupportedExternalOperation(
                f"unsupported SNMP action: {request.action}"
            )

        if request.operation is ExternalOperation.LAUNCHER:
            if self.launcher is None:
                raise UnsupportedExternalOperation("launcher transport is not configured")
            return self.launcher.execute(request)

        if request.operation is ExternalOperation.RADIUS_DISCONNECT:
            if self.chillispot is None:
                raise UnsupportedExternalOperation("RADIUS control client is not configured")
            if request.provider != "chilli_spot" or request.action != "disconnect":
                raise UnsupportedExternalOperation(
                    "RADIUS Disconnect is only enabled for the audited ChilliSpot path"
                )
            if (
                isinstance(radius_identifier, bool)
                or not isinstance(radius_identifier, int)
                or not 0 <= radius_identifier <= 255
            ):
                raise ValueError("radius_identifier must be an integer from 0 to 255")
            if not isinstance(radius_secret, str) or not radius_secret:
                raise ValueError("radius_secret must be a non-empty string")
            params = request.parameters
            username = params.get("User-Name")
            if not isinstance(username, str) or not username.strip():
                raise ValueError("ChilliSpot request must contain User-Name")
            return self.chillispot.disconnect(
                disconnect_ip=params["disconnect_ip"],
                disconnect_port=params["disconnect_port"],
                username=username,
                identifier=radius_identifier,
                secret=radius_secret,
            )

        # In particular, do not execute RSH envelopes as subprocess/shell text.
        raise UnsupportedExternalOperation(
            f"no executable transport for operation {request.operation.value!r}"
        )
