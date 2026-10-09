from __future__ import annotations

import pytest

from atd_radius.domain.ras_external import (
    ExternalOperation,
    ProviderOperationRequest,
    build_chillispot_disconnect_request,
    build_portmaster_disconnect_request,
    build_pppd_disconnect_request,
)
from atd_radius.infrastructure.ras_external_dispatcher import (
    RASExternalOperationDispatcher,
    UnsupportedExternalOperation,
)


class FakeSnmp:
    def __init__(self):
        self.executed = []
        self.walked = []

    def execute(self, request):
        self.executed.append(request)
        return ("snmp-result",)

    def walk_text_mapping(self, request):
        self.walked.append(request)
        return {".1.2.3.4": "Port 4"}


class FakeLauncher:
    def __init__(self):
        self.executed = []

    def execute(self, request):
        self.executed.append(request)
        return "launcher-result"


class FakeChilliSpot:
    def __init__(self):
        self.calls = []

    def disconnect(self, **kwargs):
        self.calls.append(kwargs)
        return "disconnect-ack"


def test_dispatcher_routes_snmp_set_to_snmp_transport():
    snmp = FakeSnmp()
    dispatcher = RASExternalOperationDispatcher(snmp=snmp, launcher=FakeLauncher(), chillispot=FakeChilliSpot())
    request = build_portmaster_disconnect_request(ras_ip="192.0.2.10", port=2)

    result = dispatcher.execute(request)

    assert result == ("snmp-result",)
    assert snmp.executed == [request]
    assert snmp.walked == []


def test_dispatcher_routes_snmp_walk_to_walk_mapping():
    snmp = FakeSnmp()
    dispatcher = RASExternalOperationDispatcher(snmp=snmp, launcher=FakeLauncher(), chillispot=FakeChilliSpot())
    request = ProviderOperationRequest(
        provider="cisco",
        operation=ExternalOperation.SNMP,
        action="walk",
        parameters={"ras_ip": "192.0.2.1", "walk_oid": ".1.2.3"},
    )

    result = dispatcher.execute(request)

    assert result == {".1.2.3.4": "Port 4"}
    assert snmp.walked == [request]
    assert snmp.executed == []


def test_dispatcher_routes_only_audited_launcher_providers():
    launcher = FakeLauncher()
    dispatcher = RASExternalOperationDispatcher(snmp=FakeSnmp(), launcher=launcher, chillispot=FakeChilliSpot())
    request = build_pppd_disconnect_request(
        command="/opt/ibs-addons/pppd/kill",
        ras_ip="192.0.2.2",
        port="7",
    )

    assert dispatcher.execute(request) == "launcher-result"
    assert launcher.executed == [request]


def test_dispatcher_routes_chillispot_with_secret_separate_from_request():
    client = FakeChilliSpot()
    dispatcher = RASExternalOperationDispatcher(snmp=FakeSnmp(), launcher=FakeLauncher(), chillispot=client)
    request = build_chillispot_disconnect_request(
        disconnect_ip="192.0.2.3", disconnect_port=3799, username="subscriber"
    )

    assert dispatcher.execute(
        request, radius_identifier=255, radius_secret="not-in-envelope"
    ) == "disconnect-ack"
    assert client.calls == [{
        "disconnect_ip": "192.0.2.3",
        "disconnect_port": 3799,
        "username": "subscriber",
        "identifier": 255,
        "secret": "not-in-envelope",
    }]
    assert "not-in-envelope" not in repr(request.parameters)


@pytest.mark.parametrize("identifier", [True, -1, 256, "1", None])
def test_chillispot_dispatch_rejects_invalid_radius_identifier(identifier):
    dispatcher = RASExternalOperationDispatcher(
        snmp=FakeSnmp(), launcher=FakeLauncher(), chillispot=FakeChilliSpot()
    )
    request = build_chillispot_disconnect_request(
        disconnect_ip="192.0.2.3", disconnect_port=3799, username="subscriber"
    )

    with pytest.raises(ValueError, match="radius_identifier"):
        dispatcher.execute(request, radius_identifier=identifier, radius_secret="secret")


def test_rsh_is_not_accidentally_executed_by_a_subprocess_transport():
    dispatcher = RASExternalOperationDispatcher(
        snmp=FakeSnmp(), launcher=FakeLauncher(), chillispot=FakeChilliSpot()
    )
    request = ProviderOperationRequest(
        provider="mikrotik",
        operation=ExternalOperation.RSH,
        action="disconnect",
        parameters={"host": "192.0.2.4", "command": "do not execute"},
    )

    with pytest.raises(UnsupportedExternalOperation, match="no executable transport"):
        dispatcher.execute(request)
