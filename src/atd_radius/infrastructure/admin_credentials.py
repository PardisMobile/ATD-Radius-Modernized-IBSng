"""Native A1.24 administrator password persistence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AdminCredentialConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True)
class AdminCredentialTarget:
    admin_id: int
    username: str


class AdminCredentialRepository:
    """Update only the native password field; caller owns the transaction and audit."""

    def __init__(self, conn: AdminCredentialConnection) -> None:
        self.conn = conn

    def update_password(self, username: str, password_hash: str) -> AdminCredentialTarget | None:
        row = self.conn.execute(
            """
            UPDATE admins
            SET password = %s
            WHERE username = %s
            RETURNING admin_id, username
            """,
            (password_hash, username),
        ).fetchone()
        if row is None:
            return None
        return AdminCredentialTarget(admin_id=int(row[0]), username=str(row[1]))
