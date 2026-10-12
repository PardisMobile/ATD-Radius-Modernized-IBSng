"""Native IAS event retrieval and deletion from IBSng A1.24."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


class IASEventConnection(Protocol):
    def execute(self, sql: str, params=()): ...


EVENT_TYPES = (
    "CHANGE_CREDIT",
    "CHANGE_DEPOSIT",
    "ADD_USER",
    "DELETE_USER",
    "ADD_ADMIN",
    "DELETE_ADMIN",
)


@dataclass(frozen=True, slots=True)
class IASEvent:
    event_id: int
    event_type: int
    event_date: datetime
    actor: str
    amount: Decimal | None
    destinations: str
    comment: str

    @property
    def event_type_name(self) -> str:
        if 1 <= self.event_type <= len(EVENT_TYPES):
            return EVENT_TYPES[self.event_type - 1]
        return f"UNKNOWN_{self.event_type}"


@dataclass(frozen=True, slots=True)
class PostgresIASEventRepository:
    conn: IASEventConnection

    def list_events(self, from_event_id: int, offset: int, to: int) -> list[IASEvent]:
        if offset < 0 or to < 0 or to > 50 * 1024 * 1024 or offset > to:
            raise ValueError("invalid IAS event range")
        # A1.24's DB helper omits LIMIT when from == to; reject that edge
        # rather than accidentally returning an unbounded event set.
        if offset == to:
            raise ValueError("IAS event range must have a positive length")
        if to - offset > 3000:
            raise ValueError("IAS event range cannot exceed 3000 rows")
        rows = self.conn.execute(
            """
            SELECT event_id, event_type, event_date, actor, amount, destinations, comment
            FROM ias_event
            WHERE event_id > %s
            ORDER BY event_id
            OFFSET %s LIMIT %s
            """,
            (from_event_id, offset, to - offset),
        ).fetchall()
        return [
            IASEvent(
                event_id=int(row[0]),
                event_type=int(row[1]),
                event_date=row[2],
                actor=str(row[3] or ""),
                amount=Decimal(str(row[4])) if row[4] is not None else None,
                destinations=str(row[5] or ""),
                comment=str(row[6] or ""),
            )
            for row in rows
        ]

    def delete_events(self, event_ids: list[int]) -> int:
        for event_id in event_ids:
            if not isinstance(event_id, int):
                raise ValueError("IAS event IDs must be integers")
        deleted = 0
        for event_id in event_ids:
            result = self.conn.execute(
                "DELETE FROM ias_event WHERE event_id = %s RETURNING event_id",
                (event_id,),
            ).fetchone()
            if result is not None:
                deleted += 1
        return deleted
