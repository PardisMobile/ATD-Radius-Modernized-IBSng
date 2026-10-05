from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import psycopg

from atd_radius.domain.models import User


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
            "INSERT INTO users (username, status) VALUES (%s, %s) RETURNING id, username, status",
            (username, status),
        ).fetchone()
        assert row is not None
        return UserRecord(id=row[0], username=row[1], status=row[2])

    def find_by_username(self, username: str) -> User | None:
        row = self.conn.execute(
            """
            SELECT u.id, u.username, u.status, c.password_hash, c.enabled
            FROM users AS u
            LEFT JOIN user_credentials AS c ON c.user_id = u.id
            WHERE u.username = %s
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None
        return User(
            id=row[0],
            username=row[1],
            password_hash=row[3],
            enabled=row[4] if row[4] is not None else row[2] == "active",
        )

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
            "UPDATE users SET status = %s WHERE id = %s",
            (status, user_id),
        )

    def set_password_hash(self, user_id: UUID, password_hash: str) -> None:
        self.conn.execute(
            """
            INSERT INTO user_credentials (user_id, auth_type, password_hash, enabled)
            VALUES (%s, 'password', %s, true)
            ON CONFLICT (user_id) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                enabled = true,
                updated_at = now()
            """,
            (user_id, password_hash),
        )
