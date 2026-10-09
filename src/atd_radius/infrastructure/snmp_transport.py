"""Minimal, bounded SNMPv1/v2c transport for source-derived RAS requests.

Only audited integer SETs and the Cisco IF-MIB ifDescr walk are supported.
The transport does not invent provider commands or OIDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
import math
import socket
import secrets
from time import monotonic
from typing import Callable, Mapping

from atd_radius.domain.ras_external import ExternalOperation, ProviderOperationRequest


class SnmpTransportError(RuntimeError):
    """An SNMP request failed, timed out, or received an invalid response."""

    def __init__(
        self,
        message: str,
        *,
        request_id: int | None = None,
        error_status: int | None = None,
        error_index: int | None = None,
        completed_responses: tuple["SnmpResponse", ...] = (),
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.error_status = error_status
        self.error_index = error_index
        self.completed_responses = completed_responses


@dataclass(frozen=True, slots=True)
class SnmpVarBind:
    oid: str
    asn_type: int
    value: bytes


@dataclass(frozen=True, slots=True)
class SnmpResponse:
    request_id: int
    error_status: int
    error_index: int
    varbinds: tuple[SnmpVarBind, ...]


SocketFactory = Callable[..., socket.socket]


def _tlv(tag: int, value: bytes) -> bytes:
    size = len(value)
    if size < 0x80:
        length = bytes((size,))
    else:
        encoded = size.to_bytes((size.bit_length() + 7) // 8, "big")
        length = bytes((0x80 | len(encoded),)) + encoded
    return bytes((tag,)) + length + value


def _ber_integer(value: int) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("SNMP integer must be an integer")
    if value < 0:
        raise ValueError("negative SNMP integers are not supported by this transport")
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return _tlv(0x02, raw)


def _base128(value: int) -> bytes:
    if value < 0:
        raise ValueError("OID arcs must be non-negative")
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(chunks))


def _encode_oid(oid: str) -> bytes:
    if not isinstance(oid, str) or not oid:
        raise ValueError("SNMP OID must be a non-empty string")
    parts = oid.lstrip(".").split(".")
    if len(parts) < 2 or any(not part.isdecimal() for part in parts):
        raise ValueError(f"invalid SNMP OID: {oid}")
    arcs = [int(part) for part in parts]
    if arcs[0] not in (0, 1, 2) or (arcs[0] < 2 and arcs[1] > 39):
        raise ValueError(f"invalid SNMP OID root: {oid}")
    encoded = _base128(40 * arcs[0] + arcs[1])
    encoded += b"".join(_base128(arc) for arc in arcs[2:])
    return _tlv(0x06, encoded)


def _read_tlv(data: bytes, offset: int) -> tuple[int, bytes, int]:
    if offset + 2 > len(data):
        raise SnmpTransportError("truncated BER tag/length")
    tag = data[offset]
    first = data[offset + 1]
    offset += 2
    if first & 0x80:
        count = first & 0x7F
        if count == 0 or count > 4 or offset + count > len(data):
            raise SnmpTransportError("invalid BER long-form length")
        size = int.from_bytes(data[offset : offset + count], "big")
        offset += count
        if size < 0x80:
            raise SnmpTransportError("non-canonical BER length")
    else:
        size = first
    end = offset + size
    if end > len(data):
        raise SnmpTransportError("truncated BER value")
    return tag, data[offset:end], end


def _decode_integer(value: bytes) -> int:
    if not value:
        raise SnmpTransportError("empty BER integer")
    return int.from_bytes(value, "big", signed=True)


def _decode_oid(value: bytes) -> str:
    if not value:
        raise SnmpTransportError("empty BER OID")
    arcs: list[int] = []
    current = 0
    in_arc = False
    for byte in value:
        current = (current << 7) | (byte & 0x7F)
        in_arc = True
        if not byte & 0x80:
            arcs.append(current)
            current = 0
            in_arc = False
    if in_arc or not arcs:
        raise SnmpTransportError("truncated BER OID arc")
    first = arcs.pop(0)
    if first < 40:
        root = (0, first)
    elif first < 80:
        root = (1, first - 40)
    else:
        root = (2, first - 80)
    return "." + ".".join(str(part) for part in (*root, *arcs))


def _build_set_message(
    *, version: int, community: bytes, request_id: int, oid: str, asn_type: str, value: object
) -> bytes:
    if asn_type != "i":
        raise ValueError(f"unsupported SNMP SET type: {asn_type}")
    if isinstance(value, bool) or not isinstance(value, int):
        if not (isinstance(value, str) and value.isdecimal()):
            raise ValueError("SNMP integer SET value must be an integer")
        value = int(value)
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("SNMP integer SET value is outside uint32 range")
    varbind = _tlv(0x30, _encode_oid(oid) + _ber_integer(value))
    varbind_list = _tlv(0x30, varbind)
    pdu = _tlv(
        0xA3,
        _ber_integer(request_id)
        + _ber_integer(0)
        + _ber_integer(0)
        + varbind_list,
    )
    return _tlv(0x30, _ber_integer(version) + _tlv(0x04, community) + pdu)


def _build_getnext_message(
    *, version: int, community: bytes, request_id: int, oid: str
) -> bytes:
    varbind = _tlv(0x30, _encode_oid(oid) + _tlv(0x05, b""))
    varbind_list = _tlv(0x30, varbind)
    pdu = _tlv(
        0xA1,
        _ber_integer(request_id)
        + _ber_integer(0)
        + _ber_integer(0)
        + varbind_list,
    )
    return _tlv(0x30, _ber_integer(version) + _tlv(0x04, community) + pdu)


def _oid_arcs(oid: str) -> tuple[int, ...]:
    if not isinstance(oid, str) or not oid:
        raise ValueError("SNMP OID must be a non-empty string")
    parts = oid.lstrip(".").split(".")
    if not parts or any(not part.isdecimal() for part in parts):
        raise ValueError(f"invalid SNMP OID: {oid}")
    return tuple(int(part) for part in parts)


def _parse_response(data: bytes) -> tuple[int, bytes, SnmpResponse]:
    tag, message, end = _read_tlv(data, 0)
    if tag != 0x30 or end != len(data):
        raise SnmpTransportError("invalid SNMP message envelope")
    offset = 0
    tag, raw_version, offset = _read_tlv(message, offset)
    if tag != 0x02:
        raise SnmpTransportError("SNMP response has no version")
    version = _decode_integer(raw_version)
    tag, community, offset = _read_tlv(message, offset)
    if tag != 0x04:
        raise SnmpTransportError("SNMP response has no community")
    tag, pdu, offset = _read_tlv(message, offset)
    if tag != 0xA2 or offset != len(message):
        raise SnmpTransportError("SNMP response is not a GetResponse PDU")
    pdu_offset = 0
    tag, raw_request_id, pdu_offset = _read_tlv(pdu, pdu_offset)
    if tag != 0x02:
        raise SnmpTransportError("SNMP response has no request id")
    request_id = _decode_integer(raw_request_id)
    tag, raw_status, pdu_offset = _read_tlv(pdu, pdu_offset)
    if tag != 0x02:
        raise SnmpTransportError("SNMP response has no error status")
    error_status = _decode_integer(raw_status)
    tag, raw_index, pdu_offset = _read_tlv(pdu, pdu_offset)
    if tag != 0x02:
        raise SnmpTransportError("SNMP response has no error index")
    error_index = _decode_integer(raw_index)
    tag, varbind_data, pdu_offset = _read_tlv(pdu, pdu_offset)
    if tag != 0x30 or pdu_offset != len(pdu):
        raise SnmpTransportError("SNMP response has invalid varbind list")
    varbinds: list[SnmpVarBind] = []
    var_offset = 0
    while var_offset < len(varbind_data):
        tag, varbind, var_offset = _read_tlv(varbind_data, var_offset)
        if tag != 0x30:
            raise SnmpTransportError("SNMP response has invalid varbind")
        inner = 0
        tag, raw_oid, inner = _read_tlv(varbind, inner)
        if tag != 0x06:
            raise SnmpTransportError("SNMP response varbind has invalid OID")
        value_tag, raw_value, inner = _read_tlv(varbind, inner)
        if inner != len(varbind):
            raise SnmpTransportError("SNMP response varbind has trailing bytes")
        varbinds.append(SnmpVarBind(_decode_oid(raw_oid), value_tag, raw_value))
    return version, community, SnmpResponse(request_id, error_status, error_index, tuple(varbinds))


class SnmpV1V2cSetTransport:
    """Execute audited SNMP SETs and the Cisco IF-MIB ifDescr walk.

    The transport is injectable for deterministic tests. It never chooses a
    provider branch or invents an OID/value.
    """

    def __init__(self, socket_factory: SocketFactory = socket.socket) -> None:
        self._socket_factory = socket_factory

    def execute(self, request: ProviderOperationRequest) -> tuple[SnmpResponse, ...]:
        if not isinstance(request, ProviderOperationRequest):
            raise ValueError("request must be a ProviderOperationRequest")
        if request.operation is not ExternalOperation.SNMP:
            raise ValueError("SNMP transport accepts only SNMP requests")
        params = request.parameters
        host = str(IPv4Address(str(params.get("ras_ip", params.get("host", "")))))
        port = params.get("udp_port", 161)
        community = params.get("community", "public")
        timeout = params.get("timeout", 10)
        retries = params.get("retries", 3)
        version_value = params.get("version", "1")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("SNMP UDP port must be between 1 and 65535")
        if not isinstance(community, str) or not community:
            raise ValueError("SNMP community must be non-empty")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("SNMP timeout must be finite and positive")
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0 or retries > 10:
            raise ValueError("SNMP retries must be between 0 and 10")
        version_text = str(version_value).lower()
        if version_text in {"1", "v1"}:
            version = 0
        elif version_text in {"2", "2c", "v2c"}:
            version = 1
        else:
            raise ValueError(f"unsupported SNMP version: {version_value}")
        raw_sets = params.get("sets")
        if raw_sets is None:
            raw_single = params.get("set")
            raw_sets = (raw_single,) if raw_single is not None else ()
        if not isinstance(raw_sets, (tuple, list)) or not raw_sets:
            raise ValueError("SNMP request must contain a SET or ordered SET sequence")
        sets: list[tuple[str, str, object]] = []
        for item in raw_sets:
            if not isinstance(item, Mapping):
                raise ValueError("SNMP SET entry must be a mapping")
            oid, asn_type, value = item.get("oid"), item.get("type"), item.get("value")
            if not isinstance(oid, str) or not isinstance(asn_type, str) or value is None:
                raise ValueError("SNMP SET entry requires oid, type and value")
            # Validate all requests before performing the first side effect.
            _encode_oid(oid)
            if asn_type != "i":
                raise ValueError(f"unsupported SNMP SET type: {asn_type}")
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                raise ValueError("SNMP SET integer value must be an integer")
            try:
                number = int(value)
            except ValueError as exc:
                raise ValueError("SNMP SET integer value must be an integer") from exc
            if not 0 <= number <= 0xFFFFFFFF:
                raise ValueError("SNMP SET integer value is outside uint32 range")
            sets.append((oid, asn_type, number))

        responses: list[SnmpResponse] = []
        sock = self._socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for oid, asn_type, value in sets:
                request_id = secrets.randbelow(0x7FFFFFFE) + 1
                packet = _build_set_message(
                    version=version,
                    community=community.encode("utf-8"),
                    request_id=request_id,
                    oid=oid,
                    asn_type=asn_type,
                    value=value,
                )
                response = self._send_with_retries(
                    sock, packet, (host, port), version, community.encode("utf-8"),
                    request_id, oid, float(timeout), retries, tuple(responses),
                )
                responses.append(response)
        finally:
            sock.close()
        return tuple(responses)

    def walk(self, request: ProviderOperationRequest) -> tuple[SnmpVarBind, ...]:
        """Walk one source-specified subtree, bounded against malformed agents."""
        if not isinstance(request, ProviderOperationRequest):
            raise ValueError("request must be a ProviderOperationRequest")
        if request.operation is not ExternalOperation.SNMP or request.action != "walk":
            raise ValueError("SNMP walk requires an SNMP request with action='walk'")
        params = request.parameters
        host = str(IPv4Address(str(params.get("ras_ip", ""))))
        port = params.get("udp_port", 161)
        community = params.get("community", "public")
        timeout = params.get("timeout", 10)
        retries = params.get("retries", 3)
        version_value = str(params.get("version", "2c")).lower()
        base_oid = params.get("walk_oid")
        if not isinstance(base_oid, str):
            raise ValueError("SNMP walk requires walk_oid")
        _encode_oid(base_oid)
        base_arcs = _oid_arcs(base_oid)
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("SNMP UDP port must be between 1 and 65535")
        if not isinstance(community, str) or not community:
            raise ValueError("SNMP community must be non-empty")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("SNMP timeout must be finite and positive")
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0 or retries > 10:
            raise ValueError("SNMP retries must be between 0 and 10")
        if version_value in {"1", "v1"}:
            version = 0
        elif version_value in {"2", "2c", "v2c"}:
            version = 1
        else:
            raise ValueError(f"unsupported SNMP version: {version_value}")
        max_varbinds = params.get("max_varbinds", 4096)
        if isinstance(max_varbinds, bool) or not isinstance(max_varbinds, int) or not 1 <= max_varbinds <= 10000:
            raise ValueError("SNMP walk max_varbinds must be between 1 and 10000")

        community_bytes = community.encode("utf-8")
        sock = self._socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        cursor = base_oid
        seen: set[str] = set()
        results: list[SnmpVarBind] = []
        try:
            while len(results) < max_varbinds:
                request_id = secrets.randbelow(0x7FFFFFFE) + 1
                packet = _build_getnext_message(
                    version=version,
                    community=community_bytes,
                    request_id=request_id,
                    oid=cursor,
                )
                response = self._send_with_retries(
                    sock,
                    packet,
                    (host, port),
                    version,
                    community_bytes,
                    request_id,
                    cursor,
                    float(timeout),
                    retries,
                    (),
                    exact_oid=False,
                    allow_walk_end=True,
                )
                if response.error_status == 2:  # SNMPv1 noSuchName at subtree end
                    break
                if not response.varbinds:
                    raise SnmpTransportError("SNMP walk response has no varbinds")
                varbind = response.varbinds[0]
                if varbind.asn_type == 0x82:  # SNMPv2c endOfMibView
                    break
                returned_arcs = _oid_arcs(varbind.oid)
                if returned_arcs <= _oid_arcs(cursor):
                    raise SnmpTransportError("SNMP walk agent did not advance the OID")
                if returned_arcs[: len(base_arcs)] != base_arcs:
                    break
                if varbind.asn_type != 0x04:
                    raise SnmpTransportError(
                        f"ifDescr walk returned unexpected ASN type {varbind.asn_type}"
                    )
                if varbind.oid in seen:
                    raise SnmpTransportError("SNMP walk agent repeated an OID")
                seen.add(varbind.oid)
                results.append(varbind)
                cursor = varbind.oid
            else:
                raise SnmpTransportError(
                    f"SNMP walk exceeded max_varbinds={max_varbinds}"
                )
        finally:
            sock.close()
        return tuple(results)

    @staticmethod
    def _send_with_retries(
        sock: socket.socket,
        packet: bytes,
        endpoint: tuple[str, int],
        expected_version: int,
        expected_community: bytes,
        request_id: int,
        expected_oid: str,
        timeout: float,
        retries: int,
        completed: tuple[SnmpResponse, ...],
        *,
        exact_oid: bool = True,
        allow_walk_end: bool = False,
    ) -> SnmpResponse:
        for attempt in range(retries + 1):
            sock.sendto(packet, endpoint)
            deadline = monotonic() + timeout
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    data, peer = sock.recvfrom(65535)
                except socket.timeout:
                    break
                if peer[0] != endpoint[0] or peer[1] != endpoint[1]:
                    continue
                try:
                    version, community, response = _parse_response(data)
                except SnmpTransportError:
                    continue
                if response.request_id != request_id:
                    continue
                if version != expected_version or community != expected_community:
                    raise SnmpTransportError(
                        "SNMP response version/community mismatch",
                        request_id=request_id,
                        completed_responses=completed,
                    )
                if len(response.varbinds) != 1 or (
                    exact_oid and response.varbinds[0].oid != expected_oid
                ):
                    raise SnmpTransportError(
                        "SNMP response varbind does not match requested OID",
                        request_id=request_id,
                        completed_responses=completed,
                    )
                if response.error_status != 0:
                    if allow_walk_end and response.error_status == 2:
                        return response
                    raise SnmpTransportError(
                        f"SNMP agent returned error status {response.error_status}",
                        request_id=request_id,
                        error_status=response.error_status,
                        error_index=response.error_index,
                        completed_responses=completed,
                    )
                if response.varbinds[0].asn_type in {0x80, 0x81, 0x82}:
                    if allow_walk_end and response.varbinds[0].asn_type == 0x82:
                        return response
                    raise SnmpTransportError(
                        "SNMP agent returned an exception value",
                        request_id=request_id,
                        completed_responses=completed,
                    )
                return response
        raise SnmpTransportError(
            f"SNMP request timed out after {retries + 1} attempt(s)",
            request_id=request_id,
            completed_responses=completed,
        )
