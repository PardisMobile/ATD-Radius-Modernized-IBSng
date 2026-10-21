"""Bounded, shell-free adapter for the A1.24 post-commit mailbox deletion hook."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path


def delete_mailbox(command: str, username: str, timeout_seconds: float = 10.0) -> bool:
    """Run a configured mailbox-deletion wrapper after the user DB transaction commits.

    The command must be an absolute executable path. The username is passed as a
    single argv element; shell expansion and command interpolation are never used.
    """
    command = str(command or "").strip()
    username = str(username or "")
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError):
        return False
    if (
        not command
        or not Path(command).is_absolute()
        or not username.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in username)
        or not math.isfinite(timeout)
        or timeout <= 0
        or timeout > 60
    ):
        return False
    try:
        result = subprocess.run(
            [command, username],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    return result.returncode == 0
