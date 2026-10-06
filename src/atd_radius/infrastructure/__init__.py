from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    locked: bool


class UserRepository:
    """PostgreSQL persistence boundary mapped directly to IBSng A1.24 users."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    @staticmethod
    def _status_locked(row: tuple) -> bool:
        return bool(row[2])

    def create(self, username: str, status: str = "active") -> UserRecord:
        del status
        user_id = self.conn.execute("SELECT nextval('users_user_id_seq')").fetchone()[0]
        self.conn.execute(
            "INSERT INTO users (user_id, credit, owner_id, group_id) VALUES (%s, %s, NULL, NULL)",
            (user_id, 0),
        )
        self.conn.execute(
            "INSERT INTO normal_users (user_id, normal_username, normal_password) VALUES (%s, %s, %s)",
            (user_id, username, ""),
        )
        return UserRecord(id=user_id, username=username, locked=False)

    def list(self, search: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0) -> list[UserRecord]:
        conditions: list[str] = []
        params: list[object] = []
        if search:
            conditions.append("nu.normal_username ILIKE %s")
            params.append(f"%{search.strip()}%")
        if status in {"locked", "active"}:
            conditions.append(("lock_attr.user_id IS NOT NULL") if status == "locked" else ("lock_attr.user_id IS NULL"))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])
        rows = self.conn.execute(
            f"""
            SELECT u.user_id, nu.normal_username, (lock_attr.user_id IS NOT NULL)
            FROM users u
            JOIN normal_users nu ON nu.user_id = u.user_id
            LEFT JOIN user_attrs lock_attr
              ON lock_attr.user_id = u.user_id AND lock_attr.attr_name = 'lock'
            {where}
            ORDER BY nu.normal_username
            LIMIT %s OFFSET %s
            """,
            params,
        ).fetchall()
        return [UserRecord(id=row[0], username=row[1], locked=bool(row[2])) for row in rows]

    def count(self, search: str | None = None, status: str | None = None) -> int:
        conditions: list[str] = []
        params: list[object] = []
        if search:
            conditions.append("nu.normal_username ILIKE %s")
            params.append(f"%{search.strip()}%")
        if status in {"locked", "active"}:
            conditions.append(("lock_attr.user_id IS NOT NULL") if status == "locked" else ("lock_attr.user_id IS NULL"))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        row = self.conn.execute(
            f"""
            SELECT count(*)
            FROM users u
            JOIN normal_users nu ON nu.user_id = u.user_id
            LEFT JOIN user_attrs lock_attr
              ON lock_attr.user_id = u.user_id AND lock_attr.attr_name = 'lock'
            {where}
            """,
            params,
        ).fetchone()
        return int(row[0]) if row else 0

    def get_by_username(self, username: str) -> UserRecord | None:
        row = self.conn.execute(
            """
            SELECT u.user_id, nu.normal_username, (lock_attr.user_id IS NOT NULL)
            FROM users u
            JOIN normal_users nu ON nu.user_id = u.user_id
            LEFT JOIN user_attrs lock_attr
              ON lock_attr.user_id = u.user_id AND lock_attr.attr_name = 'lock'
            WHERE nu.normal_username = %s
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None
        return UserRecord(id=row[0], username=row[1], locked=bool(row[2]))

    def set_status(self, user_id: int, status: str) -> None:
        if status == "locked":
            self.conn.execute(
                "INSERT INTO user_attrs (user_id, attr_name, attr_value) VALUES (%s, 'lock', 'locked') "
                "ON CONFLICT (user_id, attr_name) DO UPDATE SET attr_value=EXCLUDED.attr_value",
                (user_id,),
            )
        elif status == "active":
            self.conn.execute(
                "DELETE FROM user_attrs WHERE user_id=%s AND attr_name='lock'",
                (user_id,),
            )
        else:
            raise ValueError("A1.24 USER state is controlled by attributes; only active/locked are supported here.")

    def get_authentication_record(self, username: str) -> tuple[int, str, bool] | None:
        row = self.conn.execute(
            "SELECT u.user_id, nu.normal_password, (lock_attr.user_id IS NOT NULL) "
            "FROM users u JOIN normal_users nu ON nu.user_id=u.user_id "
            "LEFT JOIN user_attrs lock_attr ON lock_attr.user_id=u.user_id AND lock_attr.attr_name='lock' "
            "WHERE nu.normal_username=%s",
            (username,),
        ).fetchone()
        return (int(row[0]), str(row[1]), bool(row[2])) if row else None

    def set_password(self, user_id: int, password: str) -> None:
        self.conn.execute(
            "UPDATE normal_users SET normal_password=%s WHERE user_id=%s",
            (password, user_id),
        )
