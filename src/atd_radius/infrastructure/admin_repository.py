"""Read native IBSng A1.24 administrator records, permissions, and locks."""
from __future__ import annotations

from dataclasses import dataclass

import psycopg

from atd_radius.domain.admin_permissions import AdminPermissionSet


@dataclass(frozen=True)
class NativeAdminRecord:
    admin_id: int
    username: str
    name: str | None
    comment: str | None


@dataclass(frozen=True)
class NativeAdminLock:
    lock_id: int
    locker_admin_id: int | None
    reason: str | None


class AdminRepository:
    """Read-only native-schema adapter; deliberately does not authenticate sessions."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def get_by_username(self, username: str) -> NativeAdminRecord | None:
        row = self.conn.execute(
            """
            SELECT admin_id, username, name, comment
            FROM admins
            WHERE username = %s
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None
        return NativeAdminRecord(int(row[0]), str(row[1]), row[2], row[3])

    def get_by_id(self, admin_id: int) -> NativeAdminRecord | None:
        row = self.conn.execute(
            """
            SELECT admin_id, username, name, comment
            FROM admins
            WHERE admin_id = %s
            """,
            (admin_id,),
        ).fetchone()
        if row is None:
            return None
        return NativeAdminRecord(int(row[0]), str(row[1]), row[2], row[3])

    def permissions(self, admin_id: int) -> AdminPermissionSet:
        rows = self.conn.execute(
            """
            SELECT perm_name, perm_value
            FROM admin_perms
            WHERE admin_id = %s
            ORDER BY perm_name
            """,
            (admin_id,),
        ).fetchall()
        return AdminPermissionSet({str(name): value for name, value in rows})

    def locks(self, admin_id: int) -> list[NativeAdminLock]:
        rows = self.conn.execute(
            """
            SELECT lock_id, locker_admin_id, reason
            FROM admin_locks
            WHERE admin_id = %s
            ORDER BY lock_id
            """,
            (admin_id,),
        ).fetchall()
        return [
            NativeAdminLock(int(lock_id), int(locker_id) if locker_id is not None else None, reason)
            for lock_id, locker_id, reason in rows
        ]
