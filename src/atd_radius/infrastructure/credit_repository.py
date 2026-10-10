"""Native A1.24 user-credit persistence and audited administrator credit changes."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from atd_radius.infrastructure.ias_events import is_ias_enabled


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

    def lock_targets(self, usernames: list[str]) -> list[CreditTarget]:
        """Lock a batch of native users in stable ID order to avoid lock-order deadlocks."""
        if not usernames:
            return []
        rows = self.conn.execute(
            """
            SELECT u.user_id, nu.normal_username, u.owner_id, u.credit::numeric
            FROM users u
            JOIN normal_users nu ON nu.user_id = u.user_id
            WHERE nu.normal_username = ANY(%s)
            ORDER BY u.user_id
            FOR UPDATE OF u
            """,
            (usernames,),
        ).fetchall()
        return [
            CreditTarget(
                user_id=int(row[0]),
                username=str(row[1]),
                owner_id=int(row[2]) if row[2] is not None else None,
                credit=Decimal(str(row[3] or 0)),
            )
            for row in rows
        ]

    def lock_target(self, username: str) -> CreditTarget | None:
        targets = self.lock_targets([username])
        return targets[0] if targets else None

    def record_user_creation_credit(
        self,
        user_id: int,
        *,
        admin_id: int,
        admin_username: str,
        credit: Decimal,
        remote_addr: str,
        comment: str,
        allow_negative_deposit: bool,
    ) -> None:
        """Record the A1.24 ADD_USER credit/deposit effects in the caller's transaction.

        The user row must already have been inserted with this initial credit.
        A1.24 records ADD_USER (credit action 1), then IAS ADD_USER and CHANGE_CREDIT
        events even when the initial credit is zero.
        """
        credit = Decimal(credit)
        if credit < 0:
            raise CreditUnderflowError("initial user credit cannot be negative")

        admin_row = self.conn.execute(
            "SELECT deposit::numeric FROM admins WHERE admin_id = %s FOR UPDATE",
            (admin_id,),
        ).fetchone()
        if admin_row is None:
            raise LookupError(f"administrator {admin_id} not found")
        deposit = Decimal(str(admin_row[0] or 0))
        resulting_deposit = deposit - credit
        if resulting_deposit < 0 and not allow_negative_deposit:
            raise InsufficientAdminDepositError("administrator deposit is insufficient")

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
            VALUES (%s, %s, 1, %s, %s, %s::inet, %s)
            """,
            (credit_change_id, admin_id, credit, credit, remote_addr, comment),
        )
        self.conn.execute(
            "INSERT INTO credit_change_userid (credit_change_id, user_id) VALUES (%s, %s)",
            (credit_change_id, user_id),
        )

        # Native IASActions.logEvent is a no-op when IAS_ENABLED is false.
        if is_ias_enabled(self.conn):
            for event_type, amount in ((3, Decimal("0.00")), (1, credit)):
                event_id = int(
                    self.conn.execute("SELECT nextval('ias_event_event_id')").fetchone()[0]
                )
                self.conn.execute(
                    """
                    INSERT INTO ias_event
                        (event_id, event_type, actor, amount, destinations, comment)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (event_id, event_type, admin_username, amount, str(user_id), ""),
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
        return self.apply_admin_change_many(
            [target],
            admin_id=admin_id,
            admin_username=admin_username,
            delta=delta,
            remote_addr=remote_addr,
            comment=comment,
            allow_negative_deposit=allow_negative_deposit,
        )[0]

    def apply_admin_change_many(
        self,
        targets: list[CreditTarget],
        *,
        admin_id: int,
        admin_username: str,
        delta: Decimal,
        remote_addr: str,
        comment: str,
        allow_negative_deposit: bool,
    ) -> list[Decimal]:
        """Apply one A1.24 batch credit change and all native logs atomically.

        Caller must already hold all target user row locks in stable ID order and
        must commit/rollback the encompassing transaction. Operational audit is
        appended by the API caller in the same transaction.
        """
        if not targets:
            raise ValueError("at least one user is required")
        delta = Decimal(delta)
        resulting_credits = [target.credit + delta for target in targets]
        if any(credit < 0 for credit in resulting_credits):
            raise CreditUnderflowError("user credit cannot become negative")

        admin_row = self.conn.execute(
            "SELECT deposit::numeric FROM admins WHERE admin_id = %s FOR UPDATE",
            (admin_id,),
        ).fetchone()
        if admin_row is None:
            raise LookupError(f"administrator {admin_id} not found")
        deposit = Decimal(str(admin_row[0] or 0))
        total_delta = delta * len(targets)
        resulting_deposit = deposit - total_delta
        if resulting_deposit < 0 and not allow_negative_deposit:
            raise InsufficientAdminDepositError("administrator deposit is insufficient")

        for target, resulting_credit in zip(targets, resulting_credits, strict=True):
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
            (credit_change_id, admin_id, delta, total_delta, remote_addr, comment),
        )
        for target in targets:
            self.conn.execute(
                "INSERT INTO credit_change_userid (credit_change_id, user_id) VALUES (%s, %s)",
                (credit_change_id, target.user_id),
            )

        if is_ias_enabled(self.conn):
            ias_event_id = int(
                self.conn.execute("SELECT nextval('ias_event_event_id')").fetchone()[0]
            )
            self.conn.execute(
                """
                INSERT INTO ias_event
                    (event_id, event_type, actor, amount, destinations, comment)
                VALUES (%s, 1, %s, %s, %s, %s)
                """,
                (
                    ias_event_id,
                    admin_username,
                    delta,
                    ",".join(str(target.user_id) for target in targets),
                    comment,
                ),
            )
        return resulting_credits
