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


def _response(packet, *, error_status=0, error_index=0, community_override=None):
    version, community, request_id, oid = _request_fields(packet)
    if community_override is not None:
        community = community_override
    varbind = _tlv(0x30, _encode_oid(oid) + _tlv(0x02, b"\x02"))
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
    with pytest.raises(SnmpTransportError, match="community mismatch"):
        SnmpV1V2cSetTransport(lambda *_: fake).execute(request)
    assert fake.closed


@pytest.mark.parametrize(
    "request",
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
    ],
)
def test_snmp_transport_rejects_unsupported_requests_before_socket_creation(request):
    created = []
    transport = SnmpV1V2cSetTransport(lambda *args: created.append(args))
    with pytest.raises(ValueError):
        transport.execute(request)
    assert created == []
