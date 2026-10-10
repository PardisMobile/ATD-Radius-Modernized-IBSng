"""Native IBSng A1.24 administrator creation persistence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AdminCreationConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True)
class CreatedAdmin:
    admin_id: int
    username: str


class AdminCreationRepository:
    """Create an admin using the native schema; caller owns transaction and audit."""

    def __init__(self, conn: AdminCreationConnection) -> None:
        self.conn = conn

    def create(
        self,
        *,
        username: str,
        password_hash: str,
        name: str,
        comment: str,
        creator_id: int,
    ) -> CreatedAdmin:
        admin_id = int(self.conn.execute("SELECT nextval('admins_id_seq')").fetchone()[0])
        row = self.conn.execute(
            """
            INSERT INTO admins
                (admin_id, username, password, name, comment, creator_id, deposit, due)
            VALUES (%s, %s, %s, %s, %s, %s, 0, 0)
            RETURNING admin_id, username
            """,
            (admin_id, username, password_hash, name.strip(), comment.strip(), creator_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("administrator insert returned no row")
        return CreatedAdmin(admin_id=int(row[0]), username=str(row[1]))
