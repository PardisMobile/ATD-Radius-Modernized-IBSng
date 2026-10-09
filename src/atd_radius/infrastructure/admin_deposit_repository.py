"""Native A1.24 administrator deposit adjustment and source log persistence."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class DepositConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True)
class AdminDepositTarget:
    admin_id: int
    username: str
    deposit: Decimal


class AdminDepositRepository:
    """Apply A1.24 changeDeposit effects under one database transaction."""

    def __init__(self, conn: DepositConnection) -> None:
        self.conn = conn

    def lock_target(self, username: str) -> AdminDepositTarget | None:
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
            return None
        return AdminDepositTarget(
            admin_id=int(row[0]),
            username=str(row[1]),
            deposit=Decimal(str(row[2] or 0)),
        )

    def change(
        self,
        target: AdminDepositTarget,
        *,
        actor_admin_id: int,
        actor_username: str,
        delta: Decimal,
        remote_addr: str,
        comment: str,
    ) -> Decimal:
        """Persist deposit, native admin_deposit_change, and IAS event type 2."""
        delta = Decimal(delta)
        resulting_deposit = target.deposit + delta
        change_id = int(
            self.conn.execute("SELECT nextval('admin_deposit_change_id')").fetchone()[0]
        )
        self.conn.execute(
            """
            INSERT INTO admin_deposit_change
                (admin_deposit_change_id, admin_id, to_admin_id, deposit_change, remote_addr, comment)
            VALUES (%s, %s, %s, %s, %s::inet, %s)
            """,
            (change_id, actor_admin_id, target.admin_id, delta, remote_addr, comment),
        )
        self.conn.execute(
            "UPDATE admins SET deposit = deposit + %s WHERE admin_id = %s",
            (delta, target.admin_id),
        )
        event_id = int(
            self.conn.execute("SELECT nextval('ias_event_event_id')").fetchone()[0]
        )
        self.conn.execute(
            """
            INSERT INTO ias_event
                (event_id, event_type, actor, amount, destinations, comment)
            VALUES (%s, 2, %s, %s, %s, %s)
            """,
            (event_id, actor_username, delta, target.username, ""),
        )
        return resulting_deposit
