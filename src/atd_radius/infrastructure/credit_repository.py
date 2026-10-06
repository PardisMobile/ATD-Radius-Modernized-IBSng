"""Native A1.24 user-credit persistence boundary."""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol


class CreditConnection(Protocol):
    def execute(self, sql: str, params=()): ...


class UserCreditRepository:
    """Read/change users.credit through the native A1.24 persistence contract."""

    def __init__(self, conn: CreditConnection) -> None:
        self.conn = conn

    def get(self, user_id: int) -> Decimal | None:
        row = self.conn.execute(
            "SELECT credit::numeric FROM users WHERE user_id=%s",
            (user_id,),
        ).fetchone()
        return Decimal(str(row[0])) if row is not None and row[0] is not None else None

    def change(self, user_id: int, delta: Decimal) -> Decimal:
        self.conn.execute("SELECT change_user_credit(%s, %s::numeric)", (user_id, delta))
        credit = self.get(user_id)
        if credit is None:
            raise LookupError(f"user {user_id} not found")
        return credit
