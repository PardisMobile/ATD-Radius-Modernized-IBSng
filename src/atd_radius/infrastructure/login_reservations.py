"""Durable A1.24-style login-in-progress reservations.

IBSng marks a loaded user online before the login hooks finish. In a multi-worker
RADIUS service that reservation must be shared and serialized in PostgreSQL.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class LoginReservationConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class LoginReservation:
    request_key: str
    ras_id: int
    username: str
    created_at: datetime
    ras_multi_login_allowed: bool | None


class PostgresLoginReservationRepository:
    def __init__(self, conn: LoginReservationConnection) -> None:
        self.conn = conn

    @staticmethod
    def request_key(packet, peer: tuple[str, int]) -> str:
        material = f"{peer[0]}|{peer[1]}|{packet.identifier}|{packet.authenticator.hex()}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def lock_user(self, user_id: int) -> None:
        """Serialize Access-Request admission and Accounting-Start handoff per user."""
        self.conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"login:{int(user_id)}",),
        )

    def reserve(
        self, user_id: int, ras_id: int, request_key: str, username: str,
        ras_multi_login_allowed: bool | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO atd_radius_login_reservations
                (user_id, ras_id, request_key, username, ras_multi_login_allowed)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (request_key) DO NOTHING
            """,
            (int(user_id), int(ras_id), request_key, username, ras_multi_login_allowed),
        )

    def list_active(
        self, user_id: int, exclude_request_key: str | None = None,
    ) -> tuple[LoginReservation, ...]:
        rows = self.conn.execute(
            """
            SELECT request_key, ras_id, username, created_at, ras_multi_login_allowed
            FROM atd_radius_login_reservations
            WHERE user_id=%s
            ORDER BY created_at, reservation_id
            """,
            (int(user_id),),
        ).fetchall()
        return tuple(
            LoginReservation(
                str(row[0]), int(row[1]), str(row[2]), row[3],
                bool(row[4]) if row[4] is not None else None,
            )
            for row in rows
            if str(row[0]) != exclude_request_key
        )

    def release(self, request_key: str) -> None:
        """Remove a reservation for an Access-Request that did not remain accepted.

        This is deliberately keyed by the full packet-derived request key: a
        rejection must never clear another concurrent login for the same user.
        """
        self.conn.execute(
            "DELETE FROM atd_radius_login_reservations WHERE request_key=%s",
            (request_key,),
        )

    def consume_one(self, user_id: int, ras_id: int) -> None:
        """Transfer one accepted login reservation to its newly-accounted session."""
        self.conn.execute(
            """
            WITH oldest AS (
                SELECT reservation_id
                FROM atd_radius_login_reservations
                WHERE user_id=%s AND ras_id=%s
                ORDER BY created_at, reservation_id
                LIMIT 1
                FOR UPDATE
            )
            DELETE FROM atd_radius_login_reservations AS r
            USING oldest
            WHERE r.reservation_id=oldest.reservation_id
            """,
            (int(user_id), int(ras_id)),
        )

