"""Bounded subprocess transport for source-configured PPPD/PortSlave launchers.

Commands are configured by the operator and are always executed with shell=False.
This transport never handles RSH wrappers or arbitrary user-supplied shell text.
"""
from __future__ import annotations

from dataclasses import dataclass
import shlex
import subprocess
from typing import Mapping

from atd_radius.domain.ras_external import ExternalOperation, ProviderOperationRequest


class LauncherTransportError(RuntimeError):
    """A configured launcher could not be executed within its safety boundary."""

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


@dataclass(frozen=True, slots=True)
class LauncherResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


class ConfiguredLauncherTransport:
    """Execute only source-derived launcher request envelopes with bounded time."""

    def __init__(self, *, timeout_seconds: float = 10, max_output_chars: int = 4096) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("launcher timeout must be numeric")
        if not 0 < timeout_seconds <= 300:
            raise ValueError("launcher timeout must be in (0, 300] seconds")
        if isinstance(max_output_chars, bool) or not isinstance(max_output_chars, int):
            raise ValueError("max_output_chars must be an integer")
        if not 128 <= max_output_chars <= 65536:
            raise ValueError("max_output_chars must be between 128 and 65536")
        self._timeout = float(timeout_seconds)
        self._max_output_chars = max_output_chars

    def execute(self, request: ProviderOperationRequest) -> LauncherResult:
        if not isinstance(request, ProviderOperationRequest):
            raise ValueError("request must be a ProviderOperationRequest")
        if request.operation is not ExternalOperation.LAUNCHER:
            raise ValueError("launcher transport accepts only LAUNCHER requests")
        if request.action != "disconnect":
            raise ValueError("launcher transport requires action='disconnect'")
        params = request.parameters
        command = params.get("command")
        if not isinstance(command, str) or not command.strip() or "\x00" in command:
            raise ValueError("configured launcher command must be non-empty and contain no NUL")
        try:
            command_argv = shlex.split(command, posix=True)
        except ValueError as exc:
            raise ValueError("configured launcher command has invalid quoting") from exc
        if not command_argv:
            raise ValueError("configured launcher command is empty")
        # A configured absolute executable path prevents PATH-based executable
        # substitution; any command options remain argv tokens, never shell syntax.
        if not command_argv[0].startswith("/"):
            raise ValueError("configured launcher executable must be an absolute path")
        raw_arguments = params.get("arguments")
        if not isinstance(raw_arguments, (tuple, list)):
            raise ValueError("launcher arguments must be a sequence")
        arguments: list[str] = []
        for value in raw_arguments:
            if not isinstance(value, str) or "\x00" in value:
                raise ValueError("launcher arguments must be strings without NUL")
            arguments.append(value)

        try:
            completed = subprocess.run(
                [*command_argv, *arguments],
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
            raise LauncherTransportError(
                f"configured launcher timed out after {self._timeout:g} seconds",
                timed_out=True,
            ) from exc
        except OSError as exc:
            # Do not echo argv: it can contain provider credentials in other
            # future launcher integrations.
            raise LauncherTransportError(
                f"configured launcher could not be started ({type(exc).__name__})"
            ) from exc

        return LauncherResult(
            returncode=completed.returncode,
            stdout=(completed.stdout or "")[: self._max_output_chars],
            stderr=(completed.stderr or "")[: self._max_output_chars],
        )
