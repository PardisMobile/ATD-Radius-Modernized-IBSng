import subprocess

import pytest

from atd_radius.domain.ras_external import (
    ExternalOperation,
    ProviderOperationRequest,
    build_pppd_disconnect_request,
    build_portslave_disconnect_request,
)
from atd_radius.infrastructure.launcher_transport import (
    ConfiguredLauncherTransport,
    LauncherTransportError,
)


def test_launcher_transport_executes_configured_argv_without_a_shell(monkeypatch):
    request = build_pppd_disconnect_request(
        command="/configured/addons/pppd/kill --quiet",
        ras_ip="192.0.2.51",
        port="ppp12",
    )
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="disconnected\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ConfiguredLauncherTransport(timeout_seconds=2).execute(request)

    assert result.succeeded
    assert result.stdout == "disconnected\n"
    assert seen["argv"] == [
        "/configured/addons/pppd/kill",
        "--quiet",
        "192.0.2.51",
        "ppp12",
    ]
    assert seen["shell"] is False
    assert seen["timeout"] == 2
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["close_fds"] is True


def test_launcher_transport_reports_nonzero_exit_without_claiming_success(monkeypatch):
    request = build_portslave_disconnect_request(
        command="/configured/addons/portslave/kill",
        ras_ip="192.0.2.50",
        port="7",
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(
            argv, 17, stdout="x" * 300, stderr="failed"
        ),
    )
    result = ConfiguredLauncherTransport(max_output_chars=128).execute(request)
    assert not result.succeeded
    assert result.returncode == 17
    assert len(result.stdout) == 128
    assert result.stderr == "failed"


def test_launcher_transport_turns_timeout_into_explicit_failure(monkeypatch):
    request = build_pppd_disconnect_request(
        command="/configured/addons/pppd/kill",
        ras_ip="192.0.2.51",
        port="ppp12",
    )

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(LauncherTransportError, match="timed out") as caught:
        ConfiguredLauncherTransport(timeout_seconds=1).execute(request)
    assert caught.value.timed_out


@pytest.mark.parametrize(
    "request",
    [
        ProviderOperationRequest("pppd", ExternalOperation.SNMP, "disconnect", {}),
        ProviderOperationRequest("pppd", ExternalOperation.LAUNCHER, "start", {
            "command": "/configured/kill", "arguments": ()
        }),
        ProviderOperationRequest("pppd", ExternalOperation.LAUNCHER, "disconnect", {
            "command": "kill", "arguments": ()
        }),
        ProviderOperationRequest("pppd", ExternalOperation.LAUNCHER, "disconnect", {
            "command": "/configured/kill\x00bad", "arguments": ()
        }),
        ProviderOperationRequest("pppd", ExternalOperation.LAUNCHER, "disconnect", {
            "command": "/configured/kill 'unterminated", "arguments": ()
        }),
        ProviderOperationRequest("pppd", ExternalOperation.LAUNCHER, "disconnect", {
            "command": "/configured/kill", "arguments": ("bad\x00arg",)
        }),
    ],
)
def test_launcher_transport_rejects_unsupported_or_unsafe_requests_before_execution(
    request, monkeypatch
):
    called = []
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: called.append(args))
    with pytest.raises(ValueError):
        ConfiguredLauncherTransport().execute(request)
    assert called == []


@pytest.mark.parametrize("timeout", [0, -1, 301, True])
def test_launcher_transport_validates_timeout_configuration(timeout):
    with pytest.raises(ValueError):
        ConfiguredLauncherTransport(timeout_seconds=timeout)
