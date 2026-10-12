"""Native IAS user-info projection used by the IBSng IAS handler."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class IASUserInfoConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class IASUserInfo:
    user_id: int
    owner: str
    credit: Decimal
    normal_username: str | None
    voip_username: str | None


@dataclass(frozen=True, slots=True)
class PostgresIASUserInfoRepository:
    conn: IASUserInfoConnection

    def get_many(self, user_ids: list[int]) -> list[IASUserInfo]:
        if not user_ids:
            return []
        if any(user_id <= 0 for user_id in user_ids):
            raise ValueError("user IDs must be positive integers")
        if len(set(user_ids)) != len(user_ids):
            raise ValueError("duplicate user IDs are not allowed")
        if len(user_ids) > 1000:
            raise ValueError("at most 1000 user IDs may be requested")
        rows = self.conn.execute(
            """
            SELECT u.user_id,
                   CASE WHEN u.owner_id IS NULL THEN 'root' ELSE COALESCE(a.username, '') END,
                   u.credit::numeric,
                   nu.normal_username,
                   vu.voip_username
            FROM users u
            LEFT JOIN admins a ON a.admin_id = u.owner_id
            LEFT JOIN normal_users nu ON nu.user_id = u.user_id
            LEFT JOIN voip_users vu ON vu.user_id = u.user_id
            WHERE u.user_id = ANY(%s)
            ORDER BY array_position(%s::integer[], u.user_id)
            """,
            (user_ids, user_ids),
        ).fetchall()
        result = [
            IASUserInfo(
                user_id=int(row[0]),
                owner=str(row[1] or ""),
                credit=Decimal(str(row[2] or 0)),
                normal_username=str(row[3]) if row[3] is not None else None,
                voip_username=str(row[4]) if row[4] is not None else None,
            )
            for row in rows
        ]
        if {item.user_id for item in result} != set(user_ids):
            raise LookupError("one or more IAS user IDs were not found")
        return result
