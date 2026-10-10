"""Read-only A1.24 administrator information fields that persist in PostgreSQL."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class AdminInformationConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True)
class AdminLockRecord:
    lock_id: int
    locker_admin: str | None
    reason: str | None


@dataclass(frozen=True)
class AdminInformationRecord:
    admin_id: int
    username: str
    name: str | None
    comment: str | None
    deposit: Decimal
    creator_id: int | None
    creator: str | None
    locks: tuple[AdminLockRecord, ...]


class AdminInformationRepository:
    """Expose persisted fields; volatile in-memory activity fields are intentionally omitted."""

    def __init__(self, conn: AdminInformationConnection) -> None:
        self.conn = conn

    def list_usernames(self) -> list[str]:
        rows = self.conn.execute("SELECT username FROM admins ORDER BY username").fetchall()
        return [str(row[0]) for row in rows]

    def update_info(self, username: str, name: str, comment: str) -> AdminInformationRecord | None:
        row = self.conn.execute(
            "SELECT admin_id FROM admins WHERE username = %s FOR UPDATE",
            (username,),
        ).fetchone()
        if row is None:
            return None
        self.conn.execute(
            "UPDATE admins SET name = %s, comment = %s WHERE admin_id = %s",
            (name, comment, int(row[0])),
        )
        return self.get_by_username(username)

    def lock_admin(self, username: str, *, reason: str, locker_admin_id: int) -> AdminInformationRecord | None:
        row = self.conn.execute(
            "SELECT admin_id FROM admins WHERE username = %s FOR UPDATE", (username,)
        ).fetchone()
        if row is None:
            return None
        admin_id = int(row[0])
        lock_id = int(self.conn.execute("SELECT nextval('admin_locks_lock_id_seq')").fetchone()[0])
        self.conn.execute(
            "INSERT INTO admin_locks (lock_id, admin_id, reason, locker_admin_id) VALUES (%s, %s, %s, %s)",
            (lock_id, admin_id, reason, locker_admin_id),
        )
        return self.get_by_username(username)

    def unlock_admin(self, username: str, lock_id: int) -> AdminInformationRecord | None:
        row = self.conn.execute(
            "SELECT admin_id FROM admins WHERE username = %s FOR UPDATE", (username,)
        ).fetchone()
        if row is None:
            return None
        admin_id = int(row[0])
        deleted = self.conn.execute(
            "DELETE FROM admin_locks WHERE admin_id = %s AND lock_id = %s RETURNING lock_id",
            (admin_id, lock_id),
        ).fetchone()
        if deleted is None:
            return None
        return self.get_by_username(username)

    def get_permissions(self, username: str) -> tuple[tuple[str, str | None], ...] | None:
        """Return native permission rows for an existing administrator, in stable order."""
        row = self.conn.execute(
            "SELECT admin_id FROM admins WHERE username = %s",
            (username,),
        ).fetchone()
        if row is None:
            return None
        rows = self.conn.execute(
            """
            SELECT perm_name, perm_value
            FROM admin_perms
            WHERE admin_id = %s
            ORDER BY perm_name
            """,
            (int(row[0]),),
        ).fetchall()
        return tuple(
            (str(name), str(value) if value is not None else None)
            for name, value in rows
        )

    def get_by_username(self, username: str) -> AdminInformationRecord | None:
        row = self.conn.execute(
            """
            SELECT a.admin_id, a.username, a.name, a.comment, a.deposit::numeric,
                   a.creator_id, creator.username
            FROM admins a
            LEFT JOIN admins creator ON creator.admin_id = a.creator_id
            WHERE a.username = %s
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None

        lock_rows = self.conn.execute(
            """
            SELECT l.lock_id, locker.username, l.reason
            FROM admin_locks l
            LEFT JOIN admins locker ON locker.admin_id = l.locker_admin_id
            WHERE l.admin_id = %s
            ORDER BY l.lock_id
            """,
            (int(row[0]),),
        ).fetchall()
        locks = tuple(
            AdminLockRecord(
                lock_id=int(lock[0]),
                locker_admin=str(lock[1]) if lock[1] is not None else None,
                reason=lock[2],
            )
            for lock in lock_rows
        )
        return AdminInformationRecord(
            admin_id=int(row[0]),
            username=str(row[1]),
            name=row[2],
            comment=row[3],
            deposit=Decimal(str(row[4] or 0)),
            creator_id=int(row[5]) if row[5] is not None else None,
            creator=str(row[6]) if row[6] is not None else None,
            locks=locks,
        )
