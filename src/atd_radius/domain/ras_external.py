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
    if parameters is not None and not isinstance(parameters, Mapping):
        raise ValueError("parameters must be a mapping")
    return ProviderOperationRequest(
        provider=provider,
        operation=operations[0],
        action=action,
        parameters={} if parameters is None else parameters,
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
    if not isinstance(source_parameters, Mapping):
        raise ValueError("source_parameters must be a mapping")
    return build_disconnect_request(
        provider,
        strategy,
        parameters=source_parameters,
    )

def _source_integer(value: object, name: str, *, minimum: int = 0) -> int:
    """Parse a numeric source field without accepting bools or lossy coercions."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.isdecimal():
        number = int(value)
    else:
        raise ValueError(f"{name} must be an integer")
    if number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return number


def _source_ipv4(value: str, name: str = "ras_ip") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an IPv4 address")
    try:
        return str(IPv4Address(value))
    except ValueError as exc:
        raise ValueError(f"{name} must be an IPv4 address") from exc


def _validate_snmp_settings(
    community: str, timeout: float, retries: object
) -> tuple[str, float, int]:
    from math import isfinite

    if not isinstance(community, str) or not community:
        raise ValueError("SNMP community must be a non-empty string")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("SNMP timeout must be finite and positive")
    retry_count = _source_integer(retries, "SNMP retries", minimum=1)
    return community, float(timeout), retry_count


def _build_launcher_disconnect_request(
    provider: str, *, command: str, ras_ip: str, port: str
) -> ProviderOperationRequest:
    if not isinstance(command, str) or not command.strip():
        raise ValueError("launcher command must be a non-empty string")
    if not isinstance(ras_ip, str) or not ras_ip.strip():
        raise ValueError("ras_ip must be a non-empty string")
    if not isinstance(port, str) or not port.strip():
        raise ValueError("port must be a non-empty string")
    return ProviderOperationRequest(
        provider=provider,
        operation=ExternalOperation.LAUNCHER,
        action="disconnect",
        parameters={"command": command, "arguments": (ras_ip, port)},
    )


def build_portslave_disconnect_request(
    *, command: str, ras_ip: str, port: str
) -> ProviderOperationRequest:
    """Build PortSlave's source-derived launcher call: command(RAS-IP, port)."""
    return _build_launcher_disconnect_request(
        "portslave", command=command, ras_ip=ras_ip, port=port
    )


def build_pppd_disconnect_request(
    *, command: str, ras_ip: str, port: str
) -> ProviderOperationRequest:
    """Build PPPD's source-derived launcher call: command(RAS-IP, port)."""
    return _build_launcher_disconnect_request(
        "pppd", command=command, ras_ip=ras_ip, port=port
    )


def _source_cli_token(value: object, name: str) -> str:
    """Accept only an unquoted RouterOS/Cisco CLI atom; never interpolate syntax."""
    import re

    if not isinstance(value, str) or not value or not re.fullmatch(
        r"[A-Za-z0-9_.:@+-]+", value
    ):
        raise ValueError(f"{name} contains unsupported CLI characters")
    return value


def _source_cisco_port(value: object) -> str:
    """Validate Cisco port syntax while allowing source-defined slash forms."""
    import re

    if not isinstance(value, str) or not value or not re.fullmatch(
        r"[A-Za-z0-9_.:/+-]+", value
    ):
        raise ValueError("port contains unsupported Cisco port characters")
    return value


def _source_nonempty_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def resolve_cisco_snmp_port_index(
    port: str, interface_descriptions: Mapping[str, object]
) -> str | None:
    """Resolve Cisco port description to ifIndex from the source SNMP walk."""
    if not isinstance(port, str) or not port:
        raise ValueError("port must be a non-empty string")
    if not isinstance(interface_descriptions, Mapping):
        raise ValueError("interface_descriptions must be a mapping")
    index_by_description: dict[object, str] = {}
    for oid, description in interface_descriptions.items():
        if not isinstance(oid, str) or not oid:
            raise ValueError("interface description OIDs must be non-empty strings")
        suffix = oid[oid.rfind(".") + 1 :]
        if not suffix.isdecimal():
            raise ValueError("interface description OID must end in a numeric ifIndex")
        if not isinstance(description, str):
            raise ValueError("interface descriptions must be strings")
        index_by_description[description] = suffix
    return index_by_description.get(port)


def build_cisco_snmp_port_map_request(
    *,
    ras_ip: str,
    community: str = "public",
    timeout: float = 10,
    retries: object = 3,
) -> ProviderOperationRequest:
    """Build Cisco's source-derived IF-MIB ifDescr walk request envelope."""
    target = _source_ipv4(ras_ip)
    community, timeout, retry_count = _validate_snmp_settings(
        community, timeout, retries
    )
    return ProviderOperationRequest(
        provider="cisco",
        operation=ExternalOperation.SNMP,
        action="walk",
        parameters={
            "ras_ip": target,
            "community": community,
            "timeout": timeout,
            "retries": retry_count,
            "udp_port": 161,
            "version": "2c",
            "walk_oid": ".1.3.6.1.2.1.2.2.1.2",
        },
    )


def build_cisco_snmp_disconnect_request(
    *,
    ras_ip: str,
    port_index: object,
    community: str = "public",
    timeout: float = 10,
    retries: object = 3,
) -> ProviderOperationRequest:
    """Build Cisco's A1.24 SNMP kill SET using the resolved interface index."""
    target = _source_ipv4(ras_ip)
    index = _source_integer(port_index, "port_index", minimum=0)
    community, timeout, retry_count = _validate_snmp_settings(
        community, timeout, retries
    )
    return ProviderOperationRequest(
        provider="cisco",
        operation=ExternalOperation.SNMP,
        action="disconnect",
        parameters={
            "ras_ip": target,
            "community": community,
            "timeout": timeout,
            "retries": retry_count,
            "udp_port": 161,
            "version": "2c",
            "set": {
                "oid": ".1.3.6.1.4.1.9.2.1.76.0",
                "type": "i",
                "value": index,
            },
        },
    )


def build_cisco_rsh_disconnect_request(
    *, ras_ip: str, port: str, wrapper: str
) -> ProviderOperationRequest | None:
    """Build Cisco's source-defined RSH kill branch; unsupported ports return None."""
    target = _source_ipv4(ras_ip)
    port_name = _source_cisco_port(port)
    wrapper_path = _source_nonempty_text(wrapper, "wrapper")
    import re

    if port_name.startswith("Async"):
        match = re.match(r"(Async[0-9/]+)", port_name)
        if match is None:
            return None
        command = f"clear line {match.group(1)[5:]}"
    elif port_name.startswith("Serial"):
        command = f"clear interface {port_name}"
    else:
        return None
    return ProviderOperationRequest(
        provider="cisco",
        operation=ExternalOperation.RSH,
        action="disconnect",
        parameters={
            "host": target,
            "wrapper": wrapper_path,
            "arguments": (command,),
            "command": command,
        },
    )


def build_cisco_disconnect_request(
    *,
    ras_ip: str,
    port: str,
    kill_use_snmp: object = 1,
    wrapper: str | None = None,
    port_index: object | None = None,
    community: str = "public",
    timeout: float = 10,
    retries: object = 3,
) -> ProviderOperationRequest | None:
    """Select Cisco's source-configured SNMP/RSH kill branch (SNMP default)."""
    use_snmp = _source_integer(kill_use_snmp, "kill_use_snmp", minimum=0)
    if use_snmp:
        if port_index is None:
            raise ValueError("port_index is required when Cisco SNMP kill is enabled")
        return build_cisco_snmp_disconnect_request(
            ras_ip=ras_ip,
            port_index=port_index,
            community=community,
            timeout=timeout,
            retries=retries,
        )
    return build_cisco_rsh_disconnect_request(
        ras_ip=ras_ip, port=port, wrapper=wrapper
    )


def build_cisco_vpdn_interface_lookup_request(
    *,
    ras_ip: str,
    username: str,
    wrapper: str,
    max_concurrent_connections: object = 3,
) -> ProviderOperationRequest:
    """Build the exact Cisco VPDN RSH caller lookup request from A1.24."""
    target = _source_ipv4(ras_ip)
    user = _source_cli_token(username, "username")
    wrapper_path = _source_nonempty_text(wrapper, "wrapper")
    concurrency = _source_integer(
        max_concurrent_connections, "max_concurrent_connections", minimum=1
    )
    command = f"show caller user {user}"
    return ProviderOperationRequest(
        provider="cisco_vpdn",
        operation=ExternalOperation.RSH,
        action="discover_interface",
        parameters={
            "host": target,
            "wrapper": wrapper_path,
            "max_concurrent_connections": concurrency,
            "arguments": (command,),
            "command": command,
        },
    )


def resolve_cisco_vpdn_interface(
    output: str, *, username: str, remote_ip: str | None = None
) -> str | None:
    """Parse Cisco VPDN caller output using the source-defined matching rules.

    A1.24 uses the pattern User: (.+?), line (.+?), .+? remote (IPv4) with
    multiline and dot-all matching. If remote_ip is supplied, both username
    and remote IP must match; otherwise the first parsed interface is chosen.
    None signals that the caller must handle the source's interface-not-found
    error path.
    """
    import re

    if not isinstance(output, str):
        raise ValueError("output must be a string")
    user = _source_cli_token(username, "username")
    target_ip = None
    if remote_ip:
        target_ip = _source_ipv4(remote_ip, "remote_ip")
    pattern = re.compile(
        r"User: (.+?), line (.+?), .+? remote (\d+\.\d+\.\d+\.\d+)",
        re.M | re.S,
    )
    matches = pattern.findall(output)
    if target_ip is None:
        return matches[0][1] if matches else None
    for matched_username, interface, matched_ip in matches:
        if matched_username == user and matched_ip == target_ip:
            return interface
    return None


def build_cisco_vpdn_disconnect_request(
    *,
    ras_ip: str,
    interface: str,
    wrapper: str,
    max_concurrent_connections: object = 3,
) -> ProviderOperationRequest:
    """Build Cisco VPDN's source-derived RSH call after interface discovery.

    A1.24 first runs 'show caller user <username>' and resolves the matching
    virtual interface (optionally matching remote IP), then runs
    'clear interface <interface>'. This builder represents only the final
    call; caller-side discovery must use the source-derived lookup behavior.
    """
    target = _source_ipv4(ras_ip)
    interface_name = _source_cli_token(interface, "interface")
    wrapper_path = _source_nonempty_text(wrapper, "wrapper")
    concurrency = _source_integer(
        max_concurrent_connections, "max_concurrent_connections", minimum=1
    )
    command = f"clear interface {interface_name}"
    return ProviderOperationRequest(
        provider="cisco_vpdn",
        operation=ExternalOperation.RSH,
        action="disconnect",
        parameters={
            "host": target,
            "wrapper": wrapper_path,
            "max_concurrent_connections": concurrency,
            "arguments": (command,),
            "command": command,
        },
    )


def build_mikrotik_disconnect_request(
    *,
    ras_ip: str,
    nas_port_type: str,
    username: str,
    user_ip: str,
    ssh_wrapper: str,
    ssh_username: str,
    ssh_password: str,
) -> ProviderOperationRequest:
    """Build MikroTik's source-derived wrapper call without executing it.

    A1.24 chooses hotspot removal only for NAS-Port-Type 'Wireless-802.11';
    every other type follows the PPP active-session removal branch. The
    wrapper receives [host, ssh_username, ssh_password, RouterOS command].
    Because the source interpolates values into an unquoted RouterOS command,
    this modern builder rejects values outside a conservative token allowlist
    instead of attempting to guess RouterOS escaping rules.
    """
    target = _source_ipv4(ras_ip)
    client_ip = _source_ipv4(user_ip, "user_ip")
    if not isinstance(nas_port_type, str) or not nas_port_type:
        raise ValueError("nas_port_type must be a non-empty string")
    user = _source_cli_token(username, "username")
    wrapper_path = _source_nonempty_text(ssh_wrapper, "ssh_wrapper")
    login = _source_nonempty_text(ssh_username, "ssh_username")
    password = _source_nonempty_text(ssh_password, "ssh_password")
    if nas_port_type == "Wireless-802.11":
        command = (
            "/ip hotspot active remove [/ip hotspot active "
            f"find user={user} address={client_ip}]"
        )
    else:
        command = (
            "/ppp active remove [/ppp active "
            f"find name={user} address={client_ip}]"
        )
    return ProviderOperationRequest(
        provider="mikrotik",
        operation=ExternalOperation.RSH,
        action="disconnect",
        parameters={
            "host": target,
            "wrapper": wrapper_path,
            "max_concurrent_connections": 3,
            "arguments": (login, password, command),
            "command": command,
            "branch": "hotspot" if nas_port_type == "Wireless-802.11" else "ppp",
        },
    )


def build_portmaster_disconnect_request(
    *,
    ras_ip: str,
    port: object,
    community: str = "public",
    timeout: float = 10,
    retries: object = 3,
) -> ProviderOperationRequest:
    """Build PortMaster's exact A1.24 SNMP interface-disable operation.

    A1.24 maps the provider NAS-Port to ifIndex int(port) + 2 and writes
    IF-MIB ifAdminStatus=down (integer 2). Defaults: SNMP v1, UDP/161,
    community public, timeout 10 and 3 retries.
    """
    target = _source_ipv4(ras_ip)
    port_number = _source_integer(port, "port")
    community, timeout, retry_count = _validate_snmp_settings(
        community, timeout, retries
    )
    return ProviderOperationRequest(
        provider="portmaster",
        operation=ExternalOperation.SNMP,
        action="disconnect",
        parameters={
            "ras_ip": target,
            "community": community,
            "timeout": timeout,
            "retries": retry_count,
            "udp_port": 161,
            "version": "1",
            "set": {
                "oid": f".1.3.6.1.2.1.2.2.1.7.{port_number + 2}",
                "type": "i",
                "value": 2,
            },
        },
    )


def build_total_control_disconnect_request(
    *,
    ras_ip: str,
    interface_index: object,
    community: str = "public",
    timeout: float = 10,
    retries: object = 3,
) -> ProviderOperationRequest:
    """Build Total Control's source-traced SNMP down/up sequence.

    A1.24 writes IF-MIB ifAdminStatus=down (2), then immediately up (1), at
    the exact USR-Interface-Index. The ordered sequence is intentional.
    """
    target = _source_ipv4(ras_ip)
    index = _source_integer(interface_index, "interface_index", minimum=1)
    community, timeout, retry_count = _validate_snmp_settings(
        community, timeout, retries
    )
    oid = f".1.3.6.1.2.1.2.2.1.7.{index}"
    return ProviderOperationRequest(
        provider="total_control",
        operation=ExternalOperation.SNMP,
        action="disconnect",
        parameters={
            "ras_ip": target,
            "community": community,
            "timeout": timeout,
            "retries": retry_count,
            "udp_port": 161,
            "version": 1,
            "sets": (
                {"oid": oid, "type": "i", "value": 2},
                {"oid": oid, "type": "i", "value": 1},
            ),
        },
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
