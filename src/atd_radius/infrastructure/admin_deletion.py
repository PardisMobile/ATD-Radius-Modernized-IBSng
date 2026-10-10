"""Source-compatible IBSng A1.24 administrator deletion and reference cleanup."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from atd_radius.infrastructure.ias_events import is_ias_enabled


class AdminDeletionConnection(Protocol):
    def execute(self, sql: str, params=()): ...


class AdminDeletionError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class DeletedAdmin:
    admin_id: int
    username: str
    deposit: Decimal


class AdminDeletionRepository:
    """Delete an admin with all native A1.24 side effects in one caller transaction."""

    def __init__(self, conn: AdminDeletionConnection) -> None:
        self.conn = conn

    def delete(self, username: str, *, deleter_username: str) -> DeletedAdmin:
        row = self.conn.execute(
            """
            SELECT admin_id, username, deposit::numeric
            FROM admins
            WHERE username = %s
            FOR UPDATE
            """,
            (username,),
        ).fetchone()
        if row is None:
            raise AdminDeletionError("admin_not_found")

        admin = DeletedAdmin(
            admin_id=int(row[0]),
            username=str(row[1]),
            deposit=Decimal(str(row[2] or 0)),
        )
        # A1.24's system account (admin_id=0) is protected by the native
        # deleteAdmin input check and by a database rule.
        if admin.username == "system" or admin.admin_id == 0:
            raise AdminDeletionError("system_admin_protected")

        admin_id = admin.admin_id

        # Preserve A1.24 side effects and FK-safe ordering. Children of saved
        # user creations are deleted before their parent save rows.
        self.conn.execute("DELETE FROM admin_locks WHERE admin_id = %s", (admin_id,))
        self.conn.execute("DELETE FROM admin_deposit_change WHERE to_admin_id = %s", (admin_id,))
        self.conn.execute("DELETE FROM admin_perms WHERE admin_id = %s", (admin_id,))
        self.conn.execute(
            """
            DELETE FROM add_user_save_details
            WHERE add_user_save_id IN (
                SELECT add_user_save_id FROM add_user_saves WHERE admin_id = %s
            )
            """,
            (admin_id,),
        )
        self.conn.execute("DELETE FROM add_user_saves WHERE admin_id = %s", (admin_id,))
        self.conn.execute("UPDATE users SET owner_id = 0 WHERE owner_id = %s", (admin_id,))
        self.conn.execute("UPDATE groups SET owner_id = 0 WHERE owner_id = %s", (admin_id,))
        self.conn.execute("UPDATE admin_locks SET locker_admin_id = 0 WHERE locker_admin_id = %s", (admin_id,))
        self.conn.execute("UPDATE credit_change SET admin_id = 0 WHERE admin_id = %s", (admin_id,))
        self.conn.execute("UPDATE admin_deposit_change SET admin_id = 0 WHERE admin_id = %s", (admin_id,))
        self.conn.execute("UPDATE user_audit_log SET admin_id = 0 WHERE admin_id = %s", (admin_id,))
        self.conn.execute("DELETE FROM admins WHERE admin_id = %s", (admin_id,))
        self.conn.execute("UPDATE admins SET creator_id = 0 WHERE creator_id = %s", (admin_id,))

        # Source IASActions.TYPES places DELETE_ADMIN at event type 6 and emits
        # no event when the native IAS_ENABLED flag is disabled.
        if is_ias_enabled(self.conn):
            event_id = int(self.conn.execute("SELECT nextval('ias_event_event_id')").fetchone()[0])
            self.conn.execute(
                """
                INSERT INTO ias_event
                    (event_id, event_type, actor, amount, destinations, comment)
                VALUES (%s, 6, %s, %s, %s, %s)
                """,
                (event_id, deleter_username, admin.deposit, admin.username, ""),
            )
        return admin
