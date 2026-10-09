"""Application use cases for explicit source-derived RAS disconnect operations.

This service is intentionally not mounted as an HTTP endpoint. The caller must
resolve the RAS configuration and target session from trusted server-side state
and enforce authorization/audit policy before invoking a disconnect method.
"""
from __future__ import annotations

from typing import Mapping

from atd_radius.domain.ras_external import (
    ProviderOperationRequest,
    build_cisco_rsh_disconnect_request,
    build_cisco_snmp_disconnect_request,
    build_cisco_snmp_port_map_request,
    build_cisco_vpdn_disconnect_request,
    build_cisco_vpdn_interface_lookup_request,
    build_mikrotik_disconnect_request,
)
from atd_radius.domain.ras_provider_adapters import (
    CISCO_EXTERNAL_ADAPTER,
    CISCO_VPDN_EXTERNAL_ADAPTER,
)
from atd_radius.infrastructure.ras_external_dispatcher import RASExternalOperationDispatcher


def _source_flag(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer source flag")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdecimal():
        result = int(value)
    else:
        raise ValueError(f"{name} must be an integer source flag")
    if result < 0:
        raise ValueError(f"{name} must not be negative")
    return result


class RASDisconnectApplicationService:
    """Orchestrate the already source-audited provider branches."""

    def __init__(self, dispatcher: RASExternalOperationDispatcher | None = None) -> None:
        self.dispatcher = dispatcher or RASExternalOperationDispatcher()

    def execute_request(
        self,
        request: ProviderOperationRequest,
        *,
        radius_identifier: int | None = None,
        radius_secret: str | None = None,
    ) -> object:
        """Execute a built request; caller owns authorization and target selection."""
        return self.dispatcher.execute(
            request,
            radius_identifier=radius_identifier,
            radius_secret=radius_secret,
        )

    def disconnect_cisco(
        self,
        *,
        ras_ip: str,
        port: str,
        kill_use_snmp: object = 1,
        wrapper: str | None = None,
        community: str = "public",
        timeout: float = 10,
        retries: int = 3,
        snmp_version: str = "2c",
    ) -> object | None:
        """Run the source-configured Cisco SNMP lookup→SET or RSH branch."""
        if _source_flag(kill_use_snmp, "cisco_kill_use_snmp"):
            lookup = build_cisco_snmp_port_map_request(
                ras_ip=ras_ip,
                community=community,
                timeout=timeout,
                retries=retries,
                version=snmp_version,
            )
            descriptions = self.execute_request(lookup)
            if not isinstance(descriptions, Mapping):
                raise TypeError("Cisco ifDescr walk did not return a mapping")
            index = CISCO_EXTERNAL_ADAPTER.resolve_snmp_port_index(port, descriptions)
            if index is None:
                raise LookupError(f"Cisco SNMP ifDescr map does not contain port {port!r}")
            request = build_cisco_snmp_disconnect_request(
                ras_ip=ras_ip,
                port_index=index,
                community=community,
                timeout=timeout,
                retries=retries,
                version=snmp_version,
            )
            return self.execute_request(request)

        if wrapper is None:
            raise ValueError("Cisco RSH wrapper is required when SNMP kill is disabled")
        request = build_cisco_rsh_disconnect_request(
            ras_ip=ras_ip,
            port=port,
            wrapper=wrapper,
        )
        if request is None:
            return None
        return self.execute_request(request)

    def disconnect_cisco_vpdn(
        self,
        *,
        ras_ip: str,
        username: str,
        wrapper: str,
        remote_ip: str | None = None,
        max_concurrent_connections: int = 3,
    ) -> object:
        """Run the canonical Cisco VPDN discovery→parse→clear-interface sequence."""
        lookup = build_cisco_vpdn_interface_lookup_request(
            ras_ip=ras_ip,
            username=username,
            wrapper=wrapper,
            max_concurrent_connections=max_concurrent_connections,
        )
        result = self.execute_request(lookup)
        output = getattr(result, "stdout", None)
        succeeded = getattr(result, "succeeded", None)
        if not isinstance(output, str):
            raise RuntimeError("Cisco VPDN RSH lookup did not return command output")
        if succeeded is not True:
            raise RuntimeError("Cisco VPDN RSH lookup failed")
        interface = CISCO_VPDN_EXTERNAL_ADAPTER.resolve_interface(
            output, username=username, remote_ip=remote_ip
        )
        if interface is None:
            raise LookupError(
                f"Cisco VPDN interface not found for user {username!r}"
            )
        request = build_cisco_vpdn_disconnect_request(
            ras_ip=ras_ip,
            interface=interface,
            wrapper=wrapper,
            max_concurrent_connections=max_concurrent_connections,
        )
        return self.execute_request(request)

    def disconnect_mikrotik(
        self,
        *,
        ras_ip: str,
        nas_port_type: str,
        username: str,
        user_ip: str,
        ssh_wrapper: str,
        ssh_username: str,
        ssh_password: str,
    ) -> object:
        """Run the source-derived MikroTik hotspot/PPP wrapper operation."""
        request = build_mikrotik_disconnect_request(
            ras_ip=ras_ip,
            nas_port_type=nas_port_type,
            username=username,
            user_ip=user_ip,
            ssh_wrapper=ssh_wrapper,
            ssh_username=ssh_username,
            ssh_password=ssh_password,
        )
        return self.execute_request(request)
