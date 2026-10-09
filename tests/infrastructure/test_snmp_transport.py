import socket

import pytest

from atd_radius.domain.ras_external import (
    ExternalOperation,
    ProviderOperationRequest,
    build_cisco_disconnect_request,
    build_total_control_disconnect_request,
)
from atd_radius.infrastructure.snmp_transport import (
    SnmpTransportError,
    SnmpV1V2cSetTransport,
    _ber_integer,
    _encode_oid,
    _read_tlv,
    _tlv,
)


def _request_fields(packet):
    tag, message, end = _read_tlv(packet, 0)
    assert tag == 0x30 and end == len(packet)
    offset = 0
    _, version_raw, offset = _read_tlv(message, offset)
    _, community, offset = _read_tlv(message, offset)
    _, pdu, offset = _read_tlv(message, offset)
    pdu_offset = 0
    _, request_id_raw, pdu_offset = _read_tlv(pdu, pdu_offset)
    _, _, pdu_offset = _read_tlv(pdu, pdu_offset)
    _, _, pdu_offset = _read_tlv(pdu, pdu_offset)
    _, varbind_list, pdu_offset = _read_tlv(pdu, pdu_offset)
    _, varbind, _ = _read_tlv(varbind_list, 0)
    _, oid_raw, _ = _read_tlv(varbind, 0)
    from atd_radius.infrastructure.snmp_transport import _decode_integer, _decode_oid

    return (
        _decode_integer(version_raw),
        community,
        _decode_integer(request_id_raw),
        _decode_oid(oid_raw),
    )


def _response(packet, *, error_status=0, error_index=0, community_override=None, asn_type=0x02, raw_value=b"\x02"):
    version, community, request_id, oid = _request_fields(packet)
    if community_override is not None:
        community = community_override
    varbind = _tlv(0x30, _encode_oid(oid) + _tlv(asn_type, raw_value))
    varbind_list = _tlv(0x30, varbind)
    pdu = _tlv(
        0xA2,
        _ber_integer(request_id)
        + _ber_integer(error_status)
        + _ber_integer(error_index)
        + varbind_list,
    )
    return _tlv(0x30, _ber_integer(version) + _tlv(0x04, community) + pdu)


class FakeSocket:
    def __init__(self, response_factory=None):
        self.response_factory = response_factory or (lambda packet, count: _response(packet))
        self.sent = []
        self.queue = []
        self.timeouts = []
        self.closed = False

    def sendto(self, packet, endpoint):
        self.sent.append((packet, endpoint))
        response = self.response_factory(packet, len(self.sent))
        if response is not None:
            self.queue.append((response, endpoint))

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recvfrom(self, size):
        if not self.queue:
            raise socket.timeout()
        return self.queue.pop(0)

    def close(self):
        self.closed = True


def test_snmp_transport_executes_cisco_source_derived_v2c_set():
    request = build_cisco_disconnect_request(
        ras_ip="192.0.2.10", port="Async1/0", port_index=17
    )
    fake = FakeSocket()
    transport = SnmpV1V2cSetTransport(lambda *_: fake)

    responses = transport.execute(request)

    assert len(responses) == 1
    assert responses[0].error_status == 0
    assert responses[0].varbinds[0].oid == ".1.3.6.1.4.1.9.2.1.76.0"
    assert _request_fields(fake.sent[0][0])[0] == 1  # SNMPv2c
    assert fake.sent[0][1] == ("192.0.2.10", 161)
    assert fake.closed


def test_snmp_transport_executes_total_control_set_sequence_in_source_order():
    request = build_total_control_disconnect_request(
        ras_ip="192.0.2.11", interface_index=42
    )
    fake = FakeSocket()
    responses = SnmpV1V2cSetTransport(lambda *_: fake).execute(request)

    assert len(responses) == 2
    assert [ _request_fields(packet)[0] for packet, _ in fake.sent] == [0, 0]
    assert [_request_fields(packet)[3] for packet, _ in fake.sent] == [
        ".1.3.6.1.2.1.2.2.1.7.42",
        ".1.3.6.1.2.1.2.2.1.7.42",
    ]
    assert all(endpoint == ("192.0.2.11", 161) for _, endpoint in fake.sent)


def test_snmp_transport_retries_timeout_and_stops_after_success():
    fake = FakeSocket(lambda packet, count: None if count == 1 else _response(packet))
    request = build_cisco_disconnect_request(
        ras_ip="192.0.2.10", port="Async1/0", port_index=17
    )
    responses = SnmpV1V2cSetTransport(lambda *_: fake).execute(request)

    assert len(fake.sent) == 2
    assert len(responses) == 1


def test_snmp_transport_reports_agent_error_and_completed_sequence():
    request = build_total_control_disconnect_request(
        ras_ip="192.0.2.11", interface_index=42
    )
    fake = FakeSocket(
        lambda packet, count: _response(packet, error_status=5, error_index=1)
        if count == 2
        else _response(packet)
    )
    with pytest.raises(SnmpTransportError) as caught:
        SnmpV1V2cSetTransport(lambda *_: fake).execute(request)

    assert caught.value.error_status == 5
    assert caught.value.error_index == 1
    assert len(caught.value.completed_responses) == 1
    assert len(fake.sent) == 2


def test_snmp_transport_rejects_wrong_community_and_closes_socket():
    request = build_cisco_disconnect_request(
        ras_ip="192.0.2.10", port="Async1/0", port_index=17, community="trusted"
    )
    fake = FakeSocket(lambda packet, count: _response(packet, community_override=b"wrong"))
    with pytest.raises(SnmpTransportError, match="version/community mismatch"):
        SnmpV1V2cSetTransport(lambda *_: fake).execute(request)
    assert fake.closed


@pytest.mark.parametrize(
    "operation_request",
    [
        ProviderOperationRequest("cisco", ExternalOperation.RSH, "disconnect", {}),
        ProviderOperationRequest(
            "cisco", ExternalOperation.SNMP, "disconnect",
            {"ras_ip": "192.0.2.1", "set": {"oid": "1.3.6.1", "type": "s", "value": "x"}},
        ),
        ProviderOperationRequest(
            "cisco", ExternalOperation.SNMP, "disconnect",
            {"ras_ip": "192.0.2.1", "set": {"oid": "not-an-oid", "type": "i", "value": 1}},
        ),
        ProviderOperationRequest(
            "cisco", ExternalOperation.SNMP, "walk",
            {"ras_ip": "192.0.2.1", "set": {"oid": "1.3.6.1", "type": "i", "value": 1}},
        ),
    ],
)
def test_snmp_transport_rejects_unsupported_requests_before_socket_creation(operation_request):
    created = []
    transport = SnmpV1V2cSetTransport(lambda *args: created.append(args))
    with pytest.raises(ValueError):
        transport.execute(operation_request)
    assert created == []


def _walk_response(packet, oid, value, *, asn_type=0x04, error_status=0):
    version, community, request_id, _ = _request_fields(packet)
    varbind = _tlv(0x30, _encode_oid(oid) + _tlv(asn_type, value))
    varbind_list = _tlv(0x30, varbind)
    pdu = _tlv(
        0xA2,
        _ber_integer(request_id)
        + _ber_integer(error_status)
        + _ber_integer(0 if error_status == 0 else 1)
        + varbind_list,
    )
    return _tlv(0x30, _ber_integer(version) + _tlv(0x04, community) + pdu)


def test_cisco_ifdescr_walk_stops_at_subtree_boundary_and_returns_descriptions():
    from atd_radius.domain.ras_external import build_cisco_snmp_port_map_request

    base = ".1.3.6.1.2.1.2.2.1.2"
    sibling = ".1.3.6.1.2.1.2.2.1.3.1"

    def response_factory(packet, count):
        if count == 1:
            return _walk_response(packet, base + ".17", b"Async1/0")
        if count == 2:
            return _walk_response(packet, base + ".18", b"Serial0/0")
        return _walk_response(packet, sibling, b"ethernetCsmacd")

    fake = FakeSocket(response_factory)
    request = build_cisco_snmp_port_map_request(ras_ip="192.0.2.10")
    values = SnmpV1V2cSetTransport(lambda *_: fake).walk(request)

    assert [(item.oid, item.value.decode()) for item in values] == [
        (base + ".17", "Async1/0"),
        (base + ".18", "Serial0/0"),
    ]
    assert len(fake.sent) == 3
    assert all(_request_fields(packet)[0] == 1 for packet, _ in fake.sent)
    assert fake.closed


def test_snmp_v1_walk_treats_no_such_name_as_normal_end_of_subtree():
    from atd_radius.domain.ras_external import build_cisco_snmp_port_map_request

    base_request = build_cisco_snmp_port_map_request(ras_ip="192.0.2.10")
    request = ProviderOperationRequest(
        base_request.provider,
        base_request.operation,
        base_request.action,
        {**base_request.parameters, "version": "1"},
    )
    fake = FakeSocket(
        lambda packet, count: _walk_response(
            packet, _request_fields(packet)[3], b"", asn_type=0x05, error_status=2
        )
    )
    values = SnmpV1V2cSetTransport(lambda *_: fake).walk(request)
    assert values == ()
    assert len(fake.sent) == 1


def test_snmp_v2c_end_of_mib_view_terminates_walk():
    from atd_radius.domain.ras_external import build_cisco_snmp_port_map_request

    request = build_cisco_snmp_port_map_request(ras_ip="192.0.2.10")
    fake = FakeSocket(
        lambda packet, count: _walk_response(
            packet, _request_fields(packet)[3], b"", asn_type=0x82
        )
    )
    assert SnmpV1V2cSetTransport(lambda *_: fake).walk(request) == ()
    assert fake.closed


def test_snmp_walk_rejects_nonadvancing_oid_and_closes_socket():
    from atd_radius.domain.ras_external import build_cisco_snmp_port_map_request

    base = ".1.3.6.1.2.1.2.2.1.2"
    request = build_cisco_snmp_port_map_request(ras_ip="192.0.2.10")
    fake = FakeSocket(lambda packet, count: _walk_response(packet, base, b"loop"))
    with pytest.raises(SnmpTransportError, match="did not advance"):
        SnmpV1V2cSetTransport(lambda *_: fake).walk(request)
    assert fake.closed


def test_snmp_walk_enforces_varbind_limit_and_closes_socket():
    from atd_radius.domain.ras_external import build_cisco_snmp_port_map_request

    base = ".1.3.6.1.2.1.2.2.1.2"
    request = build_cisco_snmp_port_map_request(ras_ip="192.0.2.10")
    request = ProviderOperationRequest(
        request.provider,
        request.operation,
        request.action,
        {**request.parameters, "max_varbinds": 1},
    )
    fake = FakeSocket(lambda packet, count: _walk_response(packet, base + ".17", b"Async1/0"))
    with pytest.raises(SnmpTransportError, match="max_varbinds=1"):
        SnmpV1V2cSetTransport(lambda *_: fake).walk(request)
    assert fake.closed


def _request_set_value(packet):
    _, message, _ = _read_tlv(packet, 0)
    offset = 0
    _, _, offset = _read_tlv(message, offset)
    _, _, offset = _read_tlv(message, offset)
    _, pdu, _ = _read_tlv(message, offset)
    pdu_offset = 0
    _, _, pdu_offset = _read_tlv(pdu, pdu_offset)
    _, _, pdu_offset = _read_tlv(pdu, pdu_offset)
    _, _, pdu_offset = _read_tlv(pdu, pdu_offset)
    _, varbind_list, _ = _read_tlv(pdu, pdu_offset)
    _, varbind, _ = _read_tlv(varbind_list, 0)
    inner = 0
    _, _, inner = _read_tlv(varbind, inner)
    tag, value, _ = _read_tlv(varbind, inner)
    return tag, int.from_bytes(value, "big", signed=True)


def test_cisco_snmp_service_runs_ifdescr_walk_then_disconnect_set():
    from atd_radius.infrastructure.snmp_transport import CiscoSnmpDisconnectService

    base = ".1.3.6.1.2.1.2.2.1.2"
    sibling = ".1.3.6.1.2.1.2.2.1.3.1"
    walk_socket = FakeSocket(
        lambda packet, count: _walk_response(
            packet,
            base + ".17" if count == 1 else sibling,
            b"Async1/0" if count == 1 else b"ethernetCsmacd",
        )
    )
    set_socket = FakeSocket()
    sockets = iter((walk_socket, set_socket))
    transport = SnmpV1V2cSetTransport(lambda *_: next(sockets))

    responses = CiscoSnmpDisconnectService(transport).disconnect(
        ras_ip="192.0.2.10", port="Async1/0"
    )

    assert len(responses) == 1
    assert walk_socket.closed and set_socket.closed
    assert len(walk_socket.sent) == 2
    assert len(set_socket.sent) == 1
    assert _request_fields(set_socket.sent[0][0])[3] == ".1.3.6.1.4.1.9.2.1.76.0"
    assert _request_set_value(set_socket.sent[0][0]) == (0x02, 17)


def test_cisco_snmp_service_does_not_set_when_port_is_not_in_ifdescr_map():
    from atd_radius.infrastructure.snmp_transport import CiscoSnmpDisconnectService

    sibling = ".1.3.6.1.2.1.2.2.1.3.1"
    walk_socket = FakeSocket(
        lambda packet, count: _walk_response(packet, sibling, b"ethernetCsmacd")
    )
    created = []
    transport = SnmpV1V2cSetTransport(
        lambda *_: (created.append(walk_socket) or walk_socket)
    )

    with pytest.raises(LookupError, match="does not contain port"):
        CiscoSnmpDisconnectService(transport).disconnect(
            ras_ip="192.0.2.10", port="Async1/0"
        )
    assert len(walk_socket.sent) == 1
    assert walk_socket.closed


def test_snmp_set_rejects_success_response_with_wrong_asn_type():
    request = build_cisco_disconnect_request(
        ras_ip="192.0.2.10", port="Async1/0", port_index=17
    )
    fake = FakeSocket(
        lambda packet, count: _response(
            packet, asn_type=0x04, raw_value=b"not-an-integer"
        )
    )
    with pytest.raises(SnmpTransportError, match="unexpected ASN type"):
        SnmpV1V2cSetTransport(lambda *_: fake).execute(request)
    assert fake.closed
