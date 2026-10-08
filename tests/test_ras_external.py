import pytest

from atd_radius.domain.ras_external import (
    ExternalOperation,
    ProviderOperationRequest,
    RecordingExternalTransport,
    build_chillispot_disconnect_request,
    build_disconnect_request,
    disconnect_operations,
)


def test_source_derived_disconnect_strategy_operation_families():
    assert disconnect_operations("snmp-port") == (ExternalOperation.SNMP,)
    assert disconnect_operations("rsh-interface") == (ExternalOperation.RSH,)
    assert disconnect_operations("launcher") == (ExternalOperation.LAUNCHER,)
    assert disconnect_operations("provider-port") == (ExternalOperation.RADIUS_DISCONNECT,)
    assert disconnect_operations("h323-cause") == (ExternalOperation.H323,)


def test_unknown_strategy_does_not_guess_an_operation():
    assert disconnect_operations("unknown") == ()
    assert build_disconnect_request("example", "unknown") is None


def test_multi_operation_strategy_is_not_collapsed_to_a_guess():
    assert disconnect_operations("snmp-or-rsh") == (
        ExternalOperation.SNMP,
        ExternalOperation.RSH,
    )
    assert build_disconnect_request("cisco", "snmp-or-rsh") is None


def test_single_operation_request_is_transport_neutral():
    request = build_disconnect_request(
        "portslave",
        "launcher",
        parameters={"ras_ip": "192.0.2.10", "port": 7},
    )
    assert request == ProviderOperationRequest(
        provider="portslave",
        operation=ExternalOperation.LAUNCHER,
        action="disconnect",
        parameters={"ras_ip": "192.0.2.10", "port": 7},
    )


def test_recording_transport_has_no_external_side_effect():
    transport = RecordingExternalTransport()
    request = ProviderOperationRequest(
        provider="portmaster",
        operation=ExternalOperation.SNMP,
        action="disconnect",
        parameters={"port": 7},
    )

    assert transport.execute(request) is None
    assert transport.requests == [request]


def test_provider_disconnect_builder_preserves_source_parameters():
    from atd_radius.domain.ras_external import build_provider_disconnect_request

    request = build_provider_disconnect_request(
        "chilli_spot",
        "provider-port",
        source_parameters={
            "disconnect_ip": "192.0.2.20",
            "disconnect_port": 1700,
            "User-Name": "alice",
        },
    )

    assert request is not None
    assert request.operation is ExternalOperation.RADIUS_DISCONNECT
    assert request.parameters["User-Name"] == "alice"
    assert request.parameters["disconnect_port"] == 1700



def test_chillispot_disconnect_builder_requires_source_fields():
    import pytest

    from atd_radius.domain.ras_external import build_chillispot_disconnect_request

    request = build_chillispot_disconnect_request(
        disconnect_ip="192.0.2.20",
        disconnect_port=1700,
        username="alice",
    )
    assert request == ProviderOperationRequest(
        provider="chilli_spot",
        operation=ExternalOperation.RADIUS_DISCONNECT,
        action="disconnect",
        parameters={
            "disconnect_ip": "192.0.2.20",
            "disconnect_port": 1700,
            "User-Name": "alice",
        },
    )
    for kwargs in (
        {"disconnect_ip": "", "disconnect_port": 1700, "username": "alice"},
        {"disconnect_ip": "192.0.2.20", "disconnect_port": 0, "username": "alice"},
        {"disconnect_ip": "192.0.2.20", "disconnect_port": 65536, "username": "alice"},
        {"disconnect_ip": "192.0.2.20", "disconnect_port": True, "username": "alice"},
        {"disconnect_ip": "192.0.2.20", "disconnect_port": 1700, "username": ""},
    ):
        with pytest.raises(ValueError):
            build_chillispot_disconnect_request(**kwargs)


def test_chillispot_disconnect_datagram_is_authenticated_and_source_scoped():
    from atd_radius.domain.radius import RadiusCode
    from atd_radius.domain.radius_codec import decode, verify_control_request
    from atd_radius.domain.ras_external import encode_chillispot_disconnect_datagram

    destination, wire = encode_chillispot_disconnect_datagram(
        disconnect_ip="192.0.2.20",
        disconnect_port=1700,
        username="alice",
        identifier=71,
        secret="shared",
    )
    decoded = decode(wire, "shared")
    assert destination == ("192.0.2.20", 1700)
    assert decoded.code is RadiusCode.DISCONNECT_REQUEST
    assert decoded.identifier == 71
    assert decoded.attributes == {"User-Name": "alice"}
    assert verify_control_request(wire, "shared")
    assert not verify_control_request(wire, "wrong")


@pytest.mark.parametrize(
    "address",
    ["radius.example.test", "2001:db8::1", "999.1.1.1"],
)
def test_chillispot_disconnect_builder_requires_ipv4_address(address):
    import pytest

    with pytest.raises(ValueError, match="IPv4"):
        build_chillispot_disconnect_request(
            disconnect_ip=address,
            disconnect_port=1700,
            username="alice",
        )


def test_chillispot_disconnect_builder_preserves_canonical_ipv4_address():
    request = build_chillispot_disconnect_request(
        disconnect_ip="192.0.2.20",
        disconnect_port=1700,
        username="alice",
    )
    assert request.parameters["disconnect_ip"] == "192.0.2.20"
