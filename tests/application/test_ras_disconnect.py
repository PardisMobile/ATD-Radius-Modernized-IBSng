from __future__ import annotations

import pytest

from atd_radius.application.ras_disconnect import RASDisconnectApplicationService
from atd_radius.domain.ras_external import ExternalOperation
from atd_radius.infrastructure.rsh_transport import RSHResult


class FakeDispatcher:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.requests = []

    def execute(self, request, **kwargs):
        self.requests.append((request, kwargs))
        if self.responses:
            return self.responses.pop(0)
        return "executed"


def test_cisco_snmp_branch_performs_walk_before_source_oid_set():
    dispatcher = FakeDispatcher([
        {".1.3.6.1.2.1.2.2.1.2.7": "Async7"},
        "set-executed",
    ])
    service = RASDisconnectApplicationService(dispatcher)

    result = service.disconnect_cisco(
        ras_ip="192.0.2.1", port="Async7", snmp_version="1"
    )

    assert result == "set-executed"
    assert len(dispatcher.requests) == 2
    lookup, _ = dispatcher.requests[0]
    disconnect, _ = dispatcher.requests[1]
    assert lookup.action == "walk"
    assert lookup.parameters["version"] == "1"
    assert disconnect.action == "disconnect"
    assert disconnect.parameters["version"] == "1"
    assert disconnect.parameters["set"]["value"] == 7


def test_cisco_snmp_branch_does_not_disconnect_unknown_port():
    dispatcher = FakeDispatcher([{}])
    service = RASDisconnectApplicationService(dispatcher)

    with pytest.raises(LookupError, match="does not contain"):
        service.disconnect_cisco(ras_ip="192.0.2.1", port="Async99")
    assert len(dispatcher.requests) == 1


def test_cisco_rsh_branch_only_runs_when_source_flag_is_disabled():
    dispatcher = FakeDispatcher(["rsh-executed"])
    service = RASDisconnectApplicationService(dispatcher)

    result = service.disconnect_cisco(
        ras_ip="192.0.2.1",
        port="Async7",
        kill_use_snmp="0",
        wrapper="/opt/ibs-addons/cisco/rsh_wrapper",
    )

    assert result == "rsh-executed"
    request, _ = dispatcher.requests[0]
    assert request.operation is ExternalOperation.RSH
    assert request.parameters["command"] == "clear line 7"


def test_cisco_vpdn_lookup_then_disconnect_uses_resolved_interface():
    dispatcher = FakeDispatcher([
        RSHResult(
            returncode=0,
            stdout="User: alice, line Vi2, address 10.0.0.2 remote 198.51.100.9",
            stderr="",
        ),
        "disconnected",
    ])
    service = RASDisconnectApplicationService(dispatcher)

    result = service.disconnect_cisco_vpdn(
        ras_ip="192.0.2.2",
        username="alice",
        remote_ip="198.51.100.9",
        wrapper="/opt/ibs-addons/cisco/rsh_wrapper",
    )

    assert result == "disconnected"
    assert len(dispatcher.requests) == 2
    assert dispatcher.requests[0][0].action == "discover_interface"
    assert dispatcher.requests[1][0].parameters["command"] == "clear interface Vi2"


def test_cisco_vpdn_fails_closed_when_lookup_finds_no_interface():
    dispatcher = FakeDispatcher([
        RSHResult(returncode=0, stdout="No caller rows", stderr="")
    ])
    service = RASDisconnectApplicationService(dispatcher)

    with pytest.raises(LookupError, match="interface not found"):
        service.disconnect_cisco_vpdn(
            ras_ip="192.0.2.2",
            username="alice",
            wrapper="/opt/ibs-addons/cisco/rsh_wrapper",
        )
    assert len(dispatcher.requests) == 1


def test_mikrotik_application_method_builds_and_dispatches_source_request():
    dispatcher = FakeDispatcher(["removed"])
    service = RASDisconnectApplicationService(dispatcher)

    result = service.disconnect_mikrotik(
        ras_ip="192.0.2.3",
        nas_port_type="Wireless-802.11",
        username="alice",
        user_ip="198.51.100.9",
        ssh_wrapper="/opt/ibs-addons/mikrotik/ssh_wrapper",
        ssh_username="operator",
        ssh_password="configured-secret",
    )

    assert result == "removed"
    request, _ = dispatcher.requests[0]
    assert request.provider == "mikrotik"
    assert request.parameters["branch"] == "hotspot"
    assert request.parameters["arguments"][-1] == request.parameters["command"]
