from atd_radius.domain.ras_external import (
    ExternalOperation,
    ProviderOperationRequest,
    RecordingExternalTransport,
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
