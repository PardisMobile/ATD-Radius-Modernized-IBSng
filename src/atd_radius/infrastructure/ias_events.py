"""Source-compatible helpers for native IBSng IAS event logging."""
from __future__ import annotations

import re
from typing import Protocol


class IASSettingsConnection(Protocol):
    def execute(self, sql: str, params=()): ...


_IAS_INTEGER_VALUE = re.compile(r"I([01])\s*\.")


def is_ias_enabled(conn: IASSettingsConnection) -> bool:
    """Read the A1.24 serialized integer flag; missing means disabled.

    The legacy defs table stores integer settings as protocol-0 pickle text
    (for example I0 followed by a newline and period). Parse only the expected
    boolean-shaped value rather than unpickling database content.
    """
    row = conn.execute(
        "SELECT value FROM defs WHERE name = %s",
        ("IAS_ENABLED",),
    ).fetchone()
    if row is None:
        return False
    match = _IAS_INTEGER_VALUE.fullmatch(str(row[0]))
    if match is None:
        raise RuntimeError("invalid serialized IAS_ENABLED definition")
    return match.group(1) == "1"
