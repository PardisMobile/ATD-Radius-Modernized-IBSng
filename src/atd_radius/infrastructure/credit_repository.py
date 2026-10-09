"""Native A1.24 user-credit persistence and audited administrator credit changes."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class CreditConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True)
class CreditTarget:
    user_id: int
    username: str
    owner_id: int | None
    credit: Decimal


class CreditUnderflowError(ValueError):
    """A credit change would make a user's credit negative."""


class InsufficientAdminDepositError(PermissionError):
    """A credit change would overdraw the administrator's deposit."""


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

    def lock_target(self, username: str) -> CreditTarget | None:
        """Lock the native user row before permission and credit checks."""
        row = self.conn.execute(
            """
            SELECT u.user_id, nu.normal_username, u.owner_id, u.credit::numeric
            FROM users u
            JOIN normal_users nu ON nu.user_id = u.user_id
            WHERE nu.normal_username = %s
            FOR UPDATE OF u
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None
        return CreditTarget(
            user_id=int(row[0]),
            username=str(row[1]),
            owner_id=int(row[2]) if row[2] is not None else None,
            credit=Decimal(str(row[3] or 0)),
        )

    def apply_admin_change(
        self,
        target: CreditTarget,
        *,
        admin_id: int,
        admin_username: str,
        delta: Decimal,
        remote_addr: str,
        comment: str,
        allow_negative_deposit: bool,
    ) -> Decimal:
        """Apply one A1.24 credit change, deposit debit, native logs, and IAS event.

        Caller must already hold the target user's row lock and must commit/rollback
        the encompassing transaction. The operational audit event is appended by
        the API caller in that same transaction.
        """
        delta = Decimal(delta)
        resulting_credit = target.credit + delta
        if resulting_credit < 0:
            raise CreditUnderflowError("user credit cannot become negative")

        admin_row = self.conn.execute(
            "SELECT deposit::numeric FROM admins WHERE admin_id = %s FOR UPDATE",
            (admin_id,),
        ).fetchone()
        if admin_row is None:
            raise LookupError(f"administrator {admin_id} not found")
        deposit = Decimal(str(admin_row[0] or 0))
        resulting_deposit = deposit - delta
        if resulting_deposit < 0 and not allow_negative_deposit:
            raise InsufficientAdminDepositError("administrator deposit is insufficient")

        self.conn.execute(
            "UPDATE users SET credit = %s WHERE user_id = %s",
            (resulting_credit, target.user_id),
        )
        self.conn.execute(
            "UPDATE admins SET deposit = %s WHERE admin_id = %s",
            (resulting_deposit, admin_id),
        )

        credit_change_id = int(
            self.conn.execute("SELECT nextval('credit_change_id')").fetchone()[0]
        )
        self.conn.execute(
            """
            INSERT INTO credit_change
                (credit_change_id, admin_id, action, per_user_credit, admin_credit, remote_addr, comment)
            VALUES (%s, %s, 2, %s, %s, %s::inet, %s)
            """,
            (credit_change_id, admin_id, delta, delta, remote_addr, comment),
        )
        self.conn.execute(
            "INSERT INTO credit_change_userid (credit_change_id, user_id) VALUES (%s, %s)",
            (credit_change_id, target.user_id),
        )

        ias_event_id = int(
            self.conn.execute("SELECT nextval('ias_event_event_id')").fetchone()[0]
        )
        self.conn.execute(
            """
            INSERT INTO ias_event
                (event_id, event_type, actor, amount, destinations, comment)
            VALUES (%s, 1, %s, %s, %s, %s)
            """,
            (ias_event_id, admin_username, delta, str(target.user_id), comment),
        )
        return resulting_credit
