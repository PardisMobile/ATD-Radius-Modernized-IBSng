"""Server-side admin sessions with revocable opaque tokens."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

import psycopg


@dataclass(frozen=True)
class AdminSessionRecord:
    session_id: int
    admin_id: int
    username: str
    expires_at: datetime
    remote_addr: str | None


class AdminSessionRepository:
    """Persist only token digests; callers own the transaction."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    @staticmethod
    def digest(token: str) -> str:
        if not token:
            raise ValueError("session token is required")
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(
        self,
        *,
        token: str,
        admin_id: int,
        expires_at: datetime,
        remote_addr: str | None,
    ) -> int:
        row = self.conn.execute(
            """
            INSERT INTO admin_sessions (admin_id, token_hash, expires_at, remote_addr)
            VALUES (%s, %s, %s, %s)
            RETURNING session_id
            """,
            (admin_id, self.digest(token), expires_at, remote_addr),
        ).fetchone()
        if row is None:
            raise RuntimeError("database did not return the new admin session id")
        return int(row[0])

    def get_active(self, token: str) -> AdminSessionRecord | None:
        row = self.conn.execute(
            """
            SELECT s.session_id, s.admin_id, a.username, s.expires_at, s.remote_addr
            FROM admin_sessions AS s
            JOIN admins AS a ON a.admin_id = s.admin_id
            WHERE s.token_hash = %s
              AND s.revoked_at IS NULL
              AND s.expires_at > CURRENT_TIMESTAMP
            """,
            (self.digest(token),),
        ).fetchone()
        if row is None:
            return None
        return AdminSessionRecord(
            session_id=int(row[0]),
            admin_id=int(row[1]),
            username=str(row[2]),
            expires_at=row[3],
            remote_addr=str(row[4]) if row[4] is not None else None,
        )

    def revoke(self, token: str) -> bool:
        row = self.conn.execute(
            """
            UPDATE admin_sessions
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE token_hash = %s AND revoked_at IS NULL
            RETURNING session_id
            """,
            (self.digest(token),),
        ).fetchone()
        return row is not None
