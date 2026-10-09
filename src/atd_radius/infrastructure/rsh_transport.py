"""Bounded, shell-free execution of source-audited A1.24 RSH wrapper envelopes.

Canonical A1.24 calls its RSH wrapper through the script launcher with
[host, *command_arguments]. This transport preserves that argv boundary while
using subprocess timeout handling directly instead of recreating the legacy
shell-assembled script-wrapper command.
"""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
import math
import shlex
import subprocess
from threading import BoundedSemaphore
from typing import Mapping

from atd_radius.domain.ras_external import ExternalOperation, ProviderOperationRequest


_ALLOWED_PROVIDERS = {"cisco", "cisco_vpdn", "mikrotik"}


class RSHTransportError(RuntimeError):
    """An audited RSH wrapper failed to start or exceeded its time bound."""

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


@dataclass(frozen=True, slots=True)
class RSHResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.stderr.strip()


class ConfiguredRSHTransport:
    """Execute only approved RAS wrapper envelopes with bounded concurrency."""

    def __init__(
        self, *, timeout_seconds: float = 20, max_output_chars: int = 4096,
        max_concurrent_connections: int = 3,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 300
        ):
            raise ValueError("RSH timeout must be finite and in (0, 300] seconds")
        if (
            isinstance(max_output_chars, bool)
            or not isinstance(max_output_chars, int)
            or not 128 <= max_output_chars <= 65536
        ):
            raise ValueError("max_output_chars must be between 128 and 65536")
        if (
            isinstance(max_concurrent_connections, bool)
            or not isinstance(max_concurrent_connections, int)
            or not 1 <= max_concurrent_connections <= 64
        ):
            raise ValueError("max_concurrent_connections must be an integer in [1, 64]")
        self._timeout = float(timeout_seconds)
        self._max_output_chars = max_output_chars
        self._slots = BoundedSemaphore(max_concurrent_connections)

    @staticmethod
    def _validate_source_command(
        request: ProviderOperationRequest,
        params: Mapping[str, object],
        arguments: list[str],
    ) -> None:
        """Reject command strings outside the source-derived provider grammar."""
        import re

        command = params.get("command")
        if not isinstance(command, str) or not arguments or arguments[-1] != command:
            raise ValueError("RSH command must match the final argv argument")

        if request.provider == "cisco":
            if len(arguments) != 1:
                raise ValueError("Cisco RSH expects one command argument")
            valid = re.fullmatch(
                r"clear line [0-9/]+|clear interface [A-Za-z0-9_.:/+-]+",
                command,
            )
        elif request.provider == "cisco_vpdn":
            if len(arguments) != 1:
                raise ValueError("Cisco VPDN RSH expects one command argument")
            valid = re.fullmatch(
                r"show caller user [A-Za-z0-9_.:@+-]+|clear interface [A-Za-z0-9_.:@+-]+",
                command,
            )
        else:
            if len(arguments) != 3:
                raise ValueError("MikroTik RSH expects username, password and command")
            valid = re.fullmatch(
                r"/ip hotspot active remove \\[/ip hotspot active find user=[A-Za-z0-9_.:@+-]+ address=(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\]"
                r"|/ppp active remove \\[/ppp active find name=[A-Za-z0-9_.:@+-]+ address=(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\]",
                command,
            )
        if valid is None:
            raise ValueError("RSH command is outside the audited provider command grammar")

    def execute(self, request: ProviderOperationRequest) -> RSHResult:
        if not isinstance(request, ProviderOperationRequest):
            raise ValueError("request must be a ProviderOperationRequest")
        if request.operation is not ExternalOperation.RSH:
            raise ValueError("RSH transport accepts only RSH requests")
        if request.provider not in _ALLOWED_PROVIDERS:
            raise ValueError(f"RSH provider is not audited: {request.provider}")
        if request.action not in {"disconnect", "discover_interface"}:
            raise ValueError(f"unsupported RSH action: {request.action}")

        params: Mapping[str, object] = request.parameters
        host = params.get("host")
        if not isinstance(host, str):
            raise ValueError("RSH host must be a literal IPv4 address")
        try:
            host = str(IPv4Address(host))
        except ValueError as exc:
            raise ValueError("RSH host must be a literal IPv4 address") from exc

        wrapper = params.get("wrapper")
        if not isinstance(wrapper, str) or not wrapper.strip() or "\x00" in wrapper:
            raise ValueError("configured RSH wrapper must be non-empty")
        try:
            wrapper_argv = shlex.split(wrapper, posix=True)
        except ValueError as exc:
            raise ValueError("configured RSH wrapper has invalid quoting") from exc
        if not wrapper_argv or not wrapper_argv[0].startswith("/"):
            raise ValueError("configured RSH wrapper executable must be an absolute path")

        raw_arguments = params.get("arguments")
        if not isinstance(raw_arguments, (tuple, list)) or not raw_arguments:
            raise ValueError("RSH arguments must be a non-empty sequence")
        arguments: list[str] = []
        for argument in raw_arguments:
            if not isinstance(argument, str) or "\x00" in argument:
                raise ValueError("RSH arguments must be strings without NUL")
            arguments.append(argument)

        requested_concurrency = params.get("max_concurrent_connections", 3)
        if (
            isinstance(requested_concurrency, bool)
            or not isinstance(requested_concurrency, int)
            or not 1 <= requested_concurrency <= 64
        ):
            raise ValueError("max_concurrent_connections must be an integer in [1, 64]")
        self._validate_source_command(request, params, arguments)

        # The instance semaphore is the hard process limit; request metadata
        # is validated against A1.24's configured concurrency value.
        argv = [*wrapper_argv, host, *arguments]
        with self._slots:
            try:
                completed = subprocess.run(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self._timeout,
                    check=False,
                    shell=False,
                    close_fds=True,
                )
            except subprocess.TimeoutExpired as exc:
                raise RSHTransportError(
                    f"configured RSH wrapper timed out after {self._timeout:g} seconds",
                    timed_out=True,
                ) from exc
            except OSError as exc:
                raise RSHTransportError(
                    f"configured RSH wrapper could not be started ({type(exc).__name__})"
                ) from exc

        return RSHResult(
            returncode=completed.returncode,
            stdout=(completed.stdout or "")[: self._max_output_chars],
            stderr=(completed.stderr or "")[: self._max_output_chars],
        )
