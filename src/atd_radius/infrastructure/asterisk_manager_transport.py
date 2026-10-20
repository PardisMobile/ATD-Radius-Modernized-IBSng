"""Bounded Asterisk Manager Interface transport for the A1.24 Hangup path."""
from __future__ import annotations
from dataclasses import dataclass
import math
import socket
from collections.abc import Callable
from ipaddress import IPv4Address
from atd_radius.domain.ras_external import ExternalOperation, ProviderOperationRequest


class AsteriskManagerTransportError(RuntimeError):
    """The Asterisk Manager connection or action failed."""


@dataclass(frozen=True, slots=True)
class AsteriskManagerResult:
    login_message: str
    hangup_message: str
    succeeded: bool = True


class AsteriskManagerTransport:
    """Authenticate to AMI and execute exactly one source-audited Hangup action."""

    def __init__(self, *, socket_factory: Callable[..., object] = socket.create_connection,
                 max_frame_bytes: int = 16384, max_frames_per_action: int = 64) -> None:
        self._socket_factory = socket_factory
        self._max_frame_bytes = max_frame_bytes
        self._max_frames_per_action = max_frames_per_action

    @staticmethod
    def _text(params, name: str) -> str:
        value = params.get(name)
        if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError(f"{name} must be non-empty and contain no control characters")
        return value

    @staticmethod
    def _parse_frame(frame: bytes) -> dict[str, str]:
        try:
            lines = frame.decode("utf-8", "strict").split("\r\n")
        except UnicodeDecodeError as exc:
            raise AsteriskManagerTransportError("Asterisk AMI returned non-UTF-8 headers") from exc
        result = {}
        for line in lines:
            if ": " in line:
                name, value = line.split(": ", 1)
                result[name.strip().lower()] = value.strip()
        return result

    def _read_frame(self, client, buffer: bytearray) -> bytes:
        while True:
            boundary = buffer.find(b"\r\n\r\n")
            if boundary >= 0:
                frame = bytes(buffer[:boundary])
                del buffer[:boundary + 4]
                return frame
            if len(buffer) >= self._max_frame_bytes:
                raise AsteriskManagerTransportError("Asterisk AMI response exceeded the frame limit")
            chunk = client.recv(min(4096, self._max_frame_bytes - len(buffer)))
            if not chunk:
                raise AsteriskManagerTransportError("Asterisk AMI closed before replying")
            buffer.extend(chunk)

    def _action(self, client, buffer: bytearray, action_id: str, fields: tuple[tuple[str, str], ...]) -> str:
        client.sendall(("".join(f"{name}: {value}\r\n" for name, value in fields) + f"ActionID: {action_id}\r\n\r\n").encode("utf-8"))
        for _ in range(self._max_frames_per_action):
            frame = self._parse_frame(self._read_frame(client, buffer))
            if frame.get("actionid") != action_id or "response" not in frame:
                continue
            if frame["response"].lower() != "success":
                raise AsteriskManagerTransportError(frame.get("message", "Asterisk AMI rejected the action"))
            return frame.get("message", "Success")
        raise AsteriskManagerTransportError("Asterisk AMI response did not match the requested ActionID")

    def execute(self, request: ProviderOperationRequest) -> AsteriskManagerResult:
        if not isinstance(request, ProviderOperationRequest):
            raise ValueError("request must be a ProviderOperationRequest")
        if request.operation is not ExternalOperation.ASTERISK_MANAGER:
            raise ValueError("Asterisk Manager transport accepts only Asterisk Manager requests")
        if request.provider != "asterisk" or request.action != "hangup":
            raise ValueError("Asterisk Manager transport accepts only the audited Asterisk Hangup action")
        params = request.parameters
        host = self._text(params, "host")
        try:
            host = str(IPv4Address(host))
            if isinstance(params.get("port"), bool):
                raise ValueError("boolean port")
            port = int(params.get("port"))
            timeout = float(params.get("timeout"))
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid Asterisk Manager endpoint configuration") from exc
        if not 1 <= port <= 65535 or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError("invalid Asterisk Manager port or timeout")
        username, secret, channel = (self._text(params, name) for name in ("username", "secret", "channel"))
        buffer = bytearray()
        try:
            with self._socket_factory((host, port), timeout=timeout) as client:
                client.settimeout(timeout)
                login = self._action(client, buffer, "1", (("Username", username), ("Secret", secret), ("Action", "Login")))
                hangup = self._action(client, buffer, "2", (("channel", channel), ("Action", "Hangup")))
        except (OSError, TimeoutError) as exc:
            raise AsteriskManagerTransportError("Asterisk Manager transport failed") from exc
        return AsteriskManagerResult(login, hangup)
