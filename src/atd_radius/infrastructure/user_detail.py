from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import psycopg


@dataclass(frozen=True)
class UserGroupRecord:
    id: int
    name: str
    comment: str | None


@dataclass(frozen=True)
class AttributeRecord:
    name: str
    value: str


@dataclass(frozen=True)
class ConnectionLogRecord:
    id: int
    login_time: str | None
    logout_time: str | None
    successful: bool
    service: int | None
    ras_id: int | None
    credit_used: Decimal | None


@dataclass(frozen=True)
class CreditChangeRecord:
    id: int
    action: int | None
    per_user_credit: Decimal | None
    change_time: str | None
    comment: str | None


class UserDetailRepository:
    """Read User Information directly from native A1.24 tables."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def groups(self, user_id: int) -> list[UserGroupRecord]:
        rows = self.conn.execute(
            """
            SELECT g.group_id, g.group_name, g.comment
            FROM groups g
            JOIN users u ON u.group_id = g.group_id
            WHERE u.user_id = %s
            """,
            (user_id,),
        ).fetchall()
        return [UserGroupRecord(*row) for row in rows]

    def attributes(self, user_id: int) -> list[AttributeRecord]:
        rows = self.conn.execute(
            """
            SELECT attr_name, attr_value
            FROM user_attrs
            WHERE user_id = %s
            ORDER BY attr_name
            """,
            (user_id,),
        ).fetchall()
        return [AttributeRecord(*row) for row in rows]

    def connection_logs(self, user_id: int, limit: int = 25) -> list[ConnectionLogRecord]:
        rows = self.conn.execute(
            """
            SELECT connection_log_id, login_time, logout_time, successful, service, ras_id, credit_used
            FROM connection_log
            WHERE user_id = %s
            ORDER BY login_time DESC NULLS LAST
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
        return [ConnectionLogRecord(
            row[0],
            row[1].isoformat() if row[1] else None,
            row[2].isoformat() if row[2] else None,
            bool(row[3]),
            row[4],
            row[5],
            row[6],
        ) for row in rows]

    def credit_changes(self, user_id: int, limit: int = 25) -> list[CreditChangeRecord]:
        rows = self.conn.execute(
            """
            SELECT c.credit_change_id, c.action, c.per_user_credit, c.change_time, c.comment
            FROM credit_change c
            JOIN credit_change_userid cu ON cu.credit_change_id = c.credit_change_id
            WHERE cu.user_id = %s
            ORDER BY c.change_time DESC NULLS LAST
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
        return [CreditChangeRecord(
            row[0],
            row[1],
            row[2],
            row[3].isoformat() if row[3] else None,
            row[4],
        ) for row in rows]
