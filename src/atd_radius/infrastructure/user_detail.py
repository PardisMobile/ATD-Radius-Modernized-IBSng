from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import psycopg


@dataclass(frozen=True)
class UserGroupRecord:
    id: UUID
    name: str
    description: str | None
    enabled: bool


@dataclass(frozen=True)
class UserServiceRecord:
    id: UUID
    name: str
    description: str | None
    enabled: bool
    assignment_enabled: bool
    starts_at: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True)
class AttributeBindingRecord:
    name: str
    value: str
    operator: str
    value_type: str
    scope_type: str
    precedence: int
    enabled: bool


@dataclass(frozen=True)
class SessionRecord:
    id: UUID
    session_key: str
    ras_name: str | None
    framed_ip: str | None
    started_at: datetime | None
    last_interim_at: datetime | None
    input_octets: int
    output_octets: int


@dataclass(frozen=True)
class CreditRecord:
    amount: Decimal
    currency: str
    kind: str
    reference: str | None
    created_at: datetime


class UserDetailRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def groups(self, user_id: UUID) -> list[UserGroupRecord]:
        rows = self.conn.execute(
            """
            SELECT g.id, g.name, g.description, g.enabled
            FROM user_groups ug
            JOIN groups g ON g.id = ug.group_id
            WHERE ug.user_id = %s
            ORDER BY g.name
            """,
            (user_id,),
        ).fetchall()
        return [UserGroupRecord(*row) for row in rows]

    def services(self, user_id: UUID) -> list[UserServiceRecord]:
        rows = self.conn.execute(
            """
            SELECT s.id, s.name, s.description, s.enabled,
                   us.enabled, us.starts_at, us.expires_at
            FROM user_services us
            JOIN services s ON s.id = us.service_id
            WHERE us.user_id = %s
            ORDER BY s.name
            """,
            (user_id,),
        ).fetchall()
        return [UserServiceRecord(*row) for row in rows]

    def attributes(self, user_id: UUID) -> list[AttributeBindingRecord]:
        rows = self.conn.execute(
            """
            SELECT a.name, a.value, a.operator, a.value_type,
                   ab.scope_type, ab.precedence, ab.enabled
            FROM attribute_bindings ab
            JOIN attributes a ON a.id = ab.attribute_id
            WHERE (ab.scope_type = 'user' AND ab.scope_id = %s)
               OR (ab.scope_type = 'group' AND ab.scope_id IN (
                    SELECT group_id FROM user_groups WHERE user_id = %s
               ))
               OR (ab.scope_type = 'service' AND ab.scope_id IN (
                    SELECT service_id FROM user_services WHERE user_id = %s AND enabled = true
               ))
            ORDER BY ab.precedence ASC, ab.scope_type, a.name
            """,
            (user_id, user_id, user_id),
        ).fetchall()
        return [AttributeBindingRecord(*row) for row in rows]

    def active_sessions(self, user_id: UUID) -> list[SessionRecord]:
        rows = self.conn.execute(
            """
            SELECT s.id, s.session_key, r.name, host(s.framed_ip),
                   s.started_at, s.last_interim_at,
                   s.input_octets, s.output_octets
            FROM sessions s
            LEFT JOIN ras r ON r.id = s.ras_id
            WHERE s.user_id = %s AND s.stopped_at IS NULL
            ORDER BY s.started_at DESC NULLS LAST
            """,
            (user_id,),
        ).fetchall()
        return [SessionRecord(*row) for row in rows]

    def credit_ledger(self, user_id: UUID, limit: int = 25) -> list[CreditRecord]:
        rows = self.conn.execute(
            """
            SELECT amount, currency, kind, reference, created_at
            FROM credit_ledger
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
        return [CreditRecord(*row) for row in rows]
