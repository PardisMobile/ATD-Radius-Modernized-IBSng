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
    assert disconnect_operations("h323-cause") == ()


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


def test_provider_operation_request_snapshots_and_freezes_parameters():
    original = {"port": 7}
    request = ProviderOperationRequest(
        provider="portmaster",
        operation=ExternalOperation.SNMP,
        action="disconnect",
        parameters=original,
    )
    original["port"] = 99
    assert request.parameters["port"] == 7
    with pytest.raises(TypeError):
        request.parameters["port"] = 8


@pytest.mark.parametrize(("provider", "action"), [("", "disconnect"), ("portmaster", "")])
def test_provider_operation_request_rejects_empty_identity_fields(provider, action):
    with pytest.raises(ValueError):
        ProviderOperationRequest(
            provider=provider,
            operation=ExternalOperation.SNMP,
            action=action,
            parameters={},
        )


def test_provider_operation_request_recursively_freezes_nested_parameters():
    nested = {"port": 7, "metadata": {"tags": ["edge", "radius"]}}
    request = ProviderOperationRequest(
        provider="portmaster",
        operation=ExternalOperation.SNMP,
        action="disconnect",
        parameters=nested,
    )
    nested["metadata"]["tags"].append("mutated")
    nested["metadata"]["port"] = 99
    assert request.parameters["metadata"]["tags"] == ("edge", "radius")
    assert "port" not in request.parameters["metadata"]
    with pytest.raises(TypeError):
        request.parameters["metadata"]["new"] = "value"


@pytest.mark.parametrize("username", [None, 7, "", "   "])
def test_chillispot_disconnect_builder_rejects_invalid_username_type_or_value(username):
    with pytest.raises(ValueError, match="username"):
        build_chillispot_disconnect_request(
            disconnect_ip="192.0.2.20",
            disconnect_port=1700,
            username=username,
        )


def test_provider_operation_request_rejects_unknown_operation_values():
    with pytest.raises(ValueError, match="operation"):
        ProviderOperationRequest(
            provider="mikrotik",
            operation="snmp",
            action="disconnect",
            parameters={"port": 7},
        )


@pytest.mark.parametrize("parameters", [None, [], "not-a-mapping", 7])
def test_provider_operation_request_rejects_non_mapping_parameters(parameters):
    with pytest.raises(ValueError, match="parameters"):
        ProviderOperationRequest(
            provider="mikrotik",
            operation=ExternalOperation.SNMP,
            action="disconnect",
            parameters=parameters,
        )


def test_provider_operation_request_freezes_nested_mutable_values():
    source = {"nested": {"items": [1, 2]}}
    request = ProviderOperationRequest(
        provider="mikrotik",
        operation=ExternalOperation.SNMP,
        action="disconnect",
        parameters=source,
    )
    source["nested"]["items"].append(3)
    assert request.parameters["nested"]["items"] == (1, 2)
    with pytest.raises(TypeError):
        request.parameters["nested"]["other"] = "blocked"


@pytest.mark.parametrize("parameters", [[], "port=7", 7])
def test_disconnect_builder_rejects_non_mapping_parameters(parameters):
    with pytest.raises(ValueError, match="parameters"):
        build_disconnect_request(
            "portmaster",
            "snmp-port",
            parameters=parameters,
        )


@pytest.mark.parametrize("source_parameters", [None, [], "bad", 3])
def test_provider_disconnect_builder_rejects_non_mapping_source_parameters(
    source_parameters,
):
    from atd_radius.domain.ras_external import build_provider_disconnect_request

    with pytest.raises(ValueError, match="source_parameters"):
        build_provider_disconnect_request(
            "portmaster",
            "snmp-port",
            source_parameters=source_parameters,
        )


def test_disconnect_builder_preserves_empty_mapping_as_valid_parameters():
    request = build_disconnect_request(
        "portmaster",
        "snmp-port",
        parameters={},
    )
    assert request is not None
    assert request.parameters == {}

def test_portmaster_disconnect_request_matches_a124_snmp_set_and_defaults():
    from atd_radius.domain.ras_external import build_portmaster_disconnect_request

    request = build_portmaster_disconnect_request(ras_ip="192.0.2.10", port="7")

    assert request.provider == "portmaster"
    assert request.operation is ExternalOperation.SNMP
    assert request.action == "disconnect"
    assert request.parameters["ras_ip"] == "192.0.2.10"
    assert request.parameters["community"] == "public"
    assert request.parameters["timeout"] == 10.0
    assert request.parameters["retries"] == 3
    assert request.parameters["udp_port"] == 161
    assert request.parameters["version"] == "1"
    assert dict(request.parameters["set"]) == {
        "oid": ".1.3.6.1.2.1.2.2.1.7.9",
        "type": "i",
        "value": 2,
    }


def test_total_control_disconnect_preserves_a124_down_then_up_sequence():
    from atd_radius.domain.ras_external import build_total_control_disconnect_request

    request = build_total_control_disconnect_request(
        ras_ip="192.0.2.11", interface_index="42"
    )

    assert request.provider == "total_control"
    assert request.operation is ExternalOperation.SNMP
    assert request.parameters["community"] == "public"
    assert request.parameters["timeout"] == 10.0
    assert request.parameters["retries"] == 3
    assert request.parameters["udp_port"] == 161
    assert request.parameters["version"] == 1
    assert [dict(item) for item in request.parameters["sets"]] == [
        {"oid": ".1.3.6.1.2.1.2.2.1.7.42", "type": "i", "value": 2},
        {"oid": ".1.3.6.1.2.1.2.2.1.7.42", "type": "i", "value": 1},
    ]


@pytest.mark.parametrize(
    ("builder_name", "arguments"),
    [
        ("portmaster", {"ras_ip": "not-an-ip", "port": 7}),
        ("portmaster", {"ras_ip": "192.0.2.10", "port": True}),
        ("portmaster", {"ras_ip": "192.0.2.10", "port": "-1"}),
        ("total_control", {"ras_ip": "192.0.2.10", "interface_index": 0}),
        ("total_control", {"ras_ip": "192.0.2.10", "interface_index": "42.5"}),
    ],
)
def test_source_derived_snmp_disconnect_builders_reject_invalid_identity(
    builder_name, arguments
):
    from atd_radius.domain.ras_external import (
        build_portmaster_disconnect_request,
        build_total_control_disconnect_request,
    )

    builder = {
        "portmaster": build_portmaster_disconnect_request,
        "total_control": build_total_control_disconnect_request,
    }[builder_name]
    with pytest.raises(ValueError):
        builder(**arguments)


@pytest.mark.parametrize(
    "settings",
    [
        {"community": ""},
        {"timeout": 0},
        {"timeout": float("inf")},
        {"timeout": True},
        {"retries": 0},
        {"retries": True},
        {"retries": "3.5"},
    ],
)
def test_source_derived_snmp_disconnect_builders_validate_settings(settings):
    from atd_radius.domain.ras_external import build_portmaster_disconnect_request

    with pytest.raises(ValueError):
        build_portmaster_disconnect_request(
            ras_ip="192.0.2.10", port=7, **settings
        )

@pytest.mark.parametrize(
    ("builder_name", "provider", "command"),
    [
        ("portslave", "portslave", "/configured/addons/portslave/kill"),
        ("pppd", "pppd", "/configured/addons/pppd/kill"),
    ],
)
def test_launcher_disconnect_builders_preserve_a124_command_and_argument_order(
    builder_name, provider, command
):
    from atd_radius.domain.ras_external import (
        build_portslave_disconnect_request,
        build_pppd_disconnect_request,
    )

    builder = {
        "portslave": build_portslave_disconnect_request,
        "pppd": build_pppd_disconnect_request,
    }[builder_name]
    request = builder(command=command, ras_ip="192.0.2.50", port="ppp7")

    assert request.provider == provider
    assert request.operation is ExternalOperation.LAUNCHER
    assert request.action == "disconnect"
    assert request.parameters["command"] == command
    assert request.parameters["arguments"] == ("192.0.2.50", "ppp7")


@pytest.mark.parametrize(
    "arguments",
    [
        {"command": "", "ras_ip": "192.0.2.50", "port": "7"},
        {"command": "/configured/kill", "ras_ip": "", "port": "7"},
        {"command": "/configured/kill", "ras_ip": "192.0.2.50", "port": ""},
    ],
)
def test_launcher_disconnect_builders_reject_missing_source_arguments(arguments):
    from atd_radius.domain.ras_external import build_portslave_disconnect_request

    with pytest.raises(ValueError):
        build_portslave_disconnect_request(**arguments)

