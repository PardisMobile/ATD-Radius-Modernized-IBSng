from __future__ import annotations

import subprocess

import pytest

from atd_radius.domain.ras_external import (
    ExternalOperation,
    ProviderOperationRequest,
    build_cisco_vpdn_disconnect_request,
    build_mikrotik_disconnect_request,
)
from atd_radius.infrastructure.rsh_transport import (
    ConfiguredRSHTransport,
    RSHTransportError,
)


def test_rsh_transport_executes_source_wrapper_argv_without_shell(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "interface cleared", "")

    monkeypatch.setattr("atd_radius.infrastructure.rsh_transport.subprocess.run", fake_run)
    request = build_cisco_vpdn_disconnect_request(
        ras_ip="192.0.2.10",
        interface="Vi2",
        wrapper="/opt/ibs-addons/cisco/rsh_wrapper",
    )

    result = ConfiguredRSHTransport().execute(request)

    assert result.succeeded
    assert calls[0][0] == [
        "/opt/ibs-addons/cisco/rsh_wrapper",
        "192.0.2.10",
        "clear interface Vi2",
    ]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["timeout"] == 20


def test_rsh_transport_passes_mikrotik_command_as_one_argument(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("atd_radius.infrastructure.rsh_transport.subprocess.run", fake_run)
    request = build_mikrotik_disconnect_request(
        ras_ip="192.0.2.11",
        nas_port_type="Wireless-802.11",
        username="customer_1",
        user_ip="198.51.100.8",
        ssh_wrapper="/opt/ibs-addons/mikrotik/ssh_wrapper",
        ssh_username="operator",
        ssh_password="configured-secret",
    )

    ConfiguredRSHTransport().execute(request)

    argv = calls[0][0]
    assert argv[0] == "/opt/ibs-addons/mikrotik/ssh_wrapper"
    assert argv[1:4] == ["192.0.2.11", "operator", "configured-secret"]
    assert argv[4] == request.parameters["command"]
    assert " " in argv[4]
    assert calls[0][1]["shell"] is False


def test_rsh_transport_rejects_shell_metacharacters_before_process(monkeypatch):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr("atd_radius.infrastructure.rsh_transport.subprocess.run", fake_run)
    request = ProviderOperationRequest(
        provider="cisco_vpdn",
        operation=ExternalOperation.RSH,
        action="disconnect",
        parameters={
            "host": "192.0.2.10",
            "wrapper": "/opt/ibs-addons/cisco/rsh_wrapper",
            "arguments": ("clear interface Vi2; reload",),
            "command": "clear interface Vi2; reload",
        },
    )

    with pytest.raises(ValueError, match="command grammar"):
        ConfiguredRSHTransport().execute(request)
    assert called is False


def test_rsh_transport_rejects_relative_wrapper_and_unknown_provider():
    transport = ConfiguredRSHTransport()
    request = ProviderOperationRequest(
        provider="mikrotik",
        operation=ExternalOperation.RSH,
        action="disconnect",
        parameters={
            "host": "192.0.2.10",
            "wrapper": "ssh_wrapper",
            "arguments": ("operator", "secret", "/ppp active remove [/ppp active find name=x address=198.51.100.1]"),
            "command": "/ppp active remove [/ppp active find name=x address=198.51.100.1]",
        },
    )
    with pytest.raises(ValueError, match="absolute path"):
        transport.execute(request)

    unknown = ProviderOperationRequest(
        provider="unknown",
        operation=ExternalOperation.RSH,
        action="disconnect",
        parameters={"host": "192.0.2.10", "wrapper": "/usr/bin/rsh", "arguments": ("cmd",), "command": "cmd"},
    )
    with pytest.raises(ValueError, match="not audited"):
        transport.execute(unknown)


def test_rsh_transport_reports_timeout(monkeypatch):
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr("atd_radius.infrastructure.rsh_transport.subprocess.run", fake_run)
    request = build_cisco_vpdn_disconnect_request(
        ras_ip="192.0.2.10",
        interface="Vi2",
        wrapper="/opt/ibs-addons/cisco/rsh_wrapper",
    )

    with pytest.raises(RSHTransportError) as exc:
        ConfiguredRSHTransport().execute(request)
    assert exc.value.timed_out
