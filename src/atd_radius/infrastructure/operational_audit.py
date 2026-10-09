from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass(frozen=True)
class OperationalAuditEvent:
    event_id: int
    occurred_at: str


class OperationalAuditRepository:
    """Append-only operational audit writer; distinct from A1.24 user_audit_log.

    Callers must supply an authenticated native administrator identity. Do not
    write bearer tokens, passwords, RADIUS secrets, or other credentials to details.
    The caller owns the surrounding transaction and must commit the event together
    with the privileged state change whenever both share the same database.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def append(
        self,
        *,
        actor_admin_id: int,
        actor_username: str,
        action: str,
        outcome: str,
        target_type: str | None = None,
        target_id: str | None = None,
        remote_addr: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> OperationalAuditEvent:
        if actor_admin_id < 0:
            raise ValueError("actor_admin_id must be non-negative")
        if not actor_username.strip():
            raise ValueError("actor_username is required")
        if not action.strip() or len(action) > 160:
            raise ValueError("action must contain 1 to 160 characters")
        if outcome not in {"success", "denied", "failed"}:
            raise ValueError("unsupported audit outcome")
        if target_type is not None and len(target_type) > 80:
            raise ValueError("target_type must be at most 80 characters")
        if target_id is not None and len(target_id) > 255:
            raise ValueError("target_id must be at most 255 characters")
        if request_id is not None and len(request_id) > 128:
            raise ValueError("request_id must be at most 128 characters")
        if details is not None and not isinstance(details, dict):
            raise ValueError("details must be an object")

        row = self.conn.execute(
            """
            INSERT INTO operational_audit_events
                (actor_admin_id, actor_username, action, outcome, target_type,
                 target_id, remote_addr, request_id, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING event_id, occurred_at
            """,
            (
                actor_admin_id,
                actor_username.strip(),
                action.strip(),
                outcome,
                target_type,
                target_id,
                remote_addr,
                request_id,
                json.dumps(details or {}, separators=(",", ":"), sort_keys=True),
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("database did not return the inserted audit event")
        return OperationalAuditEvent(
            event_id=int(row[0]),
            occurred_at=row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
        )
