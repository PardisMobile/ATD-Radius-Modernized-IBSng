from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg


@dataclass(frozen=True)
class UserRecord:
    id: UUID
    username: str
    status: str


class UserRepository:
    """PostgreSQL persistence boundary for the modernized IBSng user model."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(self, username: str, status: str = "active") -> UserRecord:
        row = self.conn.execute(
            """
            INSERT INTO users (username, status)
            VALUES (%s, %s)
            RETURNING id, username, status
            """,
            (username, status),
        ).fetchone()
        assert row is not None
        return UserRecord(id=row[0], username=row[1], status=row[2])

    def get_by_username(self, username: str) -> UserRecord | None:
        row = self.conn.execute(
            "SELECT id, username, status FROM users WHERE username = %s",
            (username,),
        ).fetchone()
        if row is None:
            return None
        return UserRecord(id=row[0], username=row[1], status=row[2])

    def set_status(self, user_id: UUID, status: str) -> None:
        self.conn.execute(
            "UPDATE users SET status = %s, updated_at = now() WHERE id = %s",
            (status, user_id),
        )
