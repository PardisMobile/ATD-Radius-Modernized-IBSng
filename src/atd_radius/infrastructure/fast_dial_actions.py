"""Source-derived persistence adapter for A1.24 FastDialActionsManager."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class FastDialActionError(ValueError):
    """Invalid input to the native addDestinationToFastDial operation."""


class Connection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class FastDialTarget:
    user_id: int
    voip_username: str
    owner_id: int | None


class FastDialActionsRepository:
    """Map the A1.24 fast-dial action manager to native user_attrs storage.

    The write path locks the user row so parallel slot changes cannot overwrite
    each other. The generic fast_dial updater deliberately suppresses native
    USER_AUDIT_LOG writes; API writes still receive the separate operational audit.
    """

    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def get_target(self, voip_username: str) -> FastDialTarget | None:
        row = self.conn.execute(
            """SELECT u.user_id, vu.voip_username, u.owner_id
               FROM users u JOIN voip_users vu ON vu.user_id = u.user_id
               WHERE vu.voip_username = %s""",
            (voip_username,),
        ).fetchone()
        return self._target(row)

    def lock_target(self, voip_username: str) -> FastDialTarget | None:
        row = self.conn.execute(
            """SELECT u.user_id, vu.voip_username, u.owner_id
               FROM users u JOIN voip_users vu ON vu.user_id = u.user_id
               WHERE vu.voip_username = %s
               FOR UPDATE OF u""",
            (voip_username,),
        ).fetchone()
        return self._target(row)

    @staticmethod
    def _target(row) -> FastDialTarget | None:
        if row is None:
            return None
        return FastDialTarget(int(row[0]), str(row[1]), row[2])

    def _slots(self, user_id: int) -> list[str]:
        row = self.conn.execute(
            "SELECT attr_value FROM user_attrs WHERE user_id = %s AND attr_name = %s",
            (user_id, "fast_dial"),
        ).fetchone()
        if row is None:
            return [""] * 10
        slots = str(row[0]).split(",")
        if len(slots) != 10:
            raise RuntimeError("stored fast_dial attribute violates A1.24 ten-slot invariant")
        return slots

    def get_destination(self, user_id: int, index: int) -> str:
        # Native getFastDialDestination catches all lookup/index failures and
        # returns an empty string. Keep that contract for negative/out-of-range
        # indexes and for a missing/unset attribute.
        try:
            return self._slots(user_id)[index]
        except (IndexError, RuntimeError):
            return ""

    def set_destination(self, user_id: int, index: int, destination: str) -> str:
        if not destination.isdigit():
            raise FastDialActionError(f"INVALID_DESTINATION: {destination}")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= 9:
            raise FastDialActionError(f"INVALID_FAST_DIAL_INDEX: {index}")
        slots = self._slots(user_id)
        slots[index] = destination
        value = ",".join(slots)
        self.conn.execute(
            """INSERT INTO user_attrs (user_id, attr_name, attr_value)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, attr_name)
               DO UPDATE SET attr_value = EXCLUDED.attr_value""",
            (user_id, "fast_dial", value),
        )
        return destination
