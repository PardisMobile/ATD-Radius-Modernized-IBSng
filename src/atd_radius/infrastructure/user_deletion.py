"""Transactional A1.24-compatible user deletion.

The repository keeps credit refund, native history/IAS, dependent-row cleanup and
base-user removal in the caller's single PostgreSQL transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from atd_radius.infrastructure.ias_events import is_ias_enabled


class UserDeletionError(ValueError):
    """A requested user deletion violates a source-defined precondition."""


class UserDeletionOnlineError(UserDeletionError):
    """A target is online or has a login in progress."""


@dataclass(frozen=True, slots=True)
class DeletionTarget:
    user_id: int
    owner_id: int | None
    credit: Decimal
    normal_username: str | None
    has_mail_quota: bool


@dataclass(frozen=True, slots=True)
class UserDeletionResult:
    targets: tuple[DeletionTarget, ...]
    refunded_credit: Decimal


class UserDeletionRepository:
    """Source-backed deletion and credit refund over native IBSng tables."""

    def __init__(self, conn) -> None:
        self.conn = conn

    def lock_targets(self, user_ids: list[int]) -> list[DeletionTarget]:
        if not user_ids:
            raise UserDeletionError("at least one user ID is required")
        if any(user_id <= 0 for user_id in user_ids):
            raise UserDeletionError("user IDs must be positive")
        if len(set(user_ids)) != len(user_ids):
            raise UserDeletionError("user IDs must be unique")

        # Share the same advisory-lock namespace as Access admission and
        # Accounting reservation handoff, preventing deletion across login-in-flight.
        for user_id in sorted(user_ids):
            self.conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"login:{int(user_id)}",),
            )

        rows = self.conn.execute(
            """
            SELECT u.user_id, u.owner_id, u.credit::numeric, nu.normal_username,
                   EXISTS (
                       SELECT 1 FROM user_attrs ua
                       WHERE ua.user_id=u.user_id AND ua.attr_name='mail_quota'
                   ) AS has_mail_quota
            FROM users u
            LEFT JOIN normal_users nu ON nu.user_id=u.user_id
            WHERE u.user_id = ANY(%s)
            ORDER BY u.user_id
            FOR UPDATE OF u
            """,
            (sorted(user_ids),),
        ).fetchall()
        targets = [
            DeletionTarget(
                user_id=int(row[0]),
                owner_id=int(row[1]) if row[1] is not None else None,
                credit=Decimal(str(row[2] or 0)),
                normal_username=str(row[3]) if row[3] is not None else None,
                has_mail_quota=bool(row[4]),
            )
            for row in rows
        ]
        if {target.user_id for target in targets} != set(user_ids):
            raise LookupError("one or more users were not found")
        return targets

    def assert_offline(self, user_ids: list[int]) -> None:
        if not user_ids:
            return
        # Durable RADIUS state covers sessions intentionally omitted from
        # connection_log; reservations cover the Access-Accept -> Accounting-Start gap.
        rows = self.conn.execute(
            """
            SELECT DISTINCT user_id FROM atd_radius_live_sessions
            WHERE user_id = ANY(%s)
              AND state->>'started' = 'true'
              AND state->>'stopped' = 'false'
            UNION
            SELECT DISTINCT user_id FROM atd_radius_login_reservations
            WHERE user_id = ANY(%s)
            UNION
            SELECT DISTINCT user_id FROM connection_log
            WHERE user_id = ANY(%s) AND logout_time IS NULL AND successful IS TRUE
            ORDER BY user_id
            """,
            (user_ids, user_ids, user_ids),
        ).fetchall()
        if rows:
            raise UserDeletionOnlineError(
                "cannot delete online or login-in-progress users: "
                + ", ".join(str(int(row[0])) for row in rows)
            )

    def delete(
        self,
        user_ids: list[int],
        *,
        admin_id: int,
        admin_username: str,
        remote_addr: str,
        comment: str,
        delete_connection_logs: bool,
        delete_audit_logs: bool,
    ) -> UserDeletionResult:
        targets = self.lock_targets(user_ids)
        ids = [target.user_id for target in targets]
        self.assert_offline(ids)

        # Match A1.24's refund: negative user credit is not charged against deposit.
        refund = sum((max(Decimal("0"), target.credit) for target in targets), Decimal("0"))
        admin_row = self.conn.execute(
            "SELECT deposit::numeric FROM admins WHERE admin_id=%s FOR UPDATE",
            (admin_id,),
        ).fetchone()
        if admin_row is None:
            raise LookupError(f"administrator {admin_id} not found")
        deposit = Decimal(str(admin_row[0] or 0))
        self.conn.execute(
            "UPDATE admins SET deposit=%s WHERE admin_id=%s",
            (deposit + refund, admin_id),
        )

        change_id = int(self.conn.execute("SELECT nextval('credit_change_id')").fetchone()[0])
        self.conn.execute(
            """
            INSERT INTO credit_change
                (credit_change_id, admin_id, action, per_user_credit, admin_credit, remote_addr, comment)
            VALUES (%s, %s, 3, 0, %s, %s::inet, %s)
            """,
            (change_id, admin_id, -refund, remote_addr, comment),
        )
        for user_id in ids:
            self.conn.execute(
                "INSERT INTO credit_change_userid (credit_change_id, user_id) VALUES (%s, %s)",
                (change_id, user_id),
            )

        # IASActions.TYPES: DELETE_USER is event type 4; no event is written when disabled.
        if is_ias_enabled(self.conn):
            event_id = int(self.conn.execute("SELECT nextval('ias_event_event_id')").fetchone()[0])
            self.conn.execute(
                """
                INSERT INTO ias_event
                    (event_id, event_type, actor, amount, destinations, comment)
                VALUES (%s, 4, %s, 0, %s, '')
                """,
                (event_id, admin_username, ",".join(str(user_id) for user_id in ids)),
            )

        self.conn.execute("DELETE FROM user_attrs WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM normal_users WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM persistent_lan_users WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM caller_id_users WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM voip_users WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM user_messages WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM admin_messages WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM web_analyzer_log WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM internet_bw_snapshot WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM atd_radius_login_reservations WHERE user_id = ANY(%s)", (ids,))
        self.conn.execute("DELETE FROM atd_radius_live_sessions WHERE user_id = ANY(%s)", (ids,))

        if delete_connection_logs:
            self.conn.execute(
                "DELETE FROM connection_log_details WHERE connection_log_id IN "
                "(SELECT connection_log_id FROM connection_log WHERE user_id = ANY(%s))",
                (ids,),
            )
            self.conn.execute("DELETE FROM connection_log WHERE user_id = ANY(%s)", (ids,))
        if delete_audit_logs:
            self.conn.execute("DELETE FROM user_audit_log WHERE user_id = ANY(%s)", (ids,))

        self.conn.execute("DELETE FROM users WHERE user_id = ANY(%s)", (ids,))
        return UserDeletionResult(tuple(targets), refund)
