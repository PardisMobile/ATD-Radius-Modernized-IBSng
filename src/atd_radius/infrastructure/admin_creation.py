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
    """Create an admin and its native A1.24 IAS event in the caller transaction."""

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
        creator_username: str,
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

        # A1.24 ias_actions.TYPES assigns ADD_ADMIN event type 5. The event is
        # part of the same transaction as the admins insert; the API caller owns
        # commit/rollback. The source event records the creator and new username.
        event_id = int(self.conn.execute("SELECT nextval('ias_event_event_id')").fetchone()[0])
        self.conn.execute(
            """
            INSERT INTO ias_event
                (event_id, event_type, actor, amount, destinations, comment)
            VALUES (%s, 5, %s, 0, %s, %s)
            """,
            (event_id, creator_username, str(row[1]), ""),
        )
        return CreatedAdmin(admin_id=int(row[0]), username=str(row[1]))
