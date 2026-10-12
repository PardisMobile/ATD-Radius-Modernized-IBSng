"""Source-backed assignment of native normal_charge and voip_charge attributes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from atd_radius.infrastructure.user_attribute_mutations import (
    AUDIT_LOG_NOVALUE,
    UserAttributeMutationRepository,
    is_user_audit_log_enabled,
)


class UserChargeConnection(Protocol):
    def execute(self, sql: str, params=()): ...


class UserChargeTargetNotFound(LookupError): pass
class UserChargeNotFound(LookupError): pass
class UserChargeTypeError(ValueError): pass
class UserChargePermissionError(PermissionError): pass


@dataclass(frozen=True, slots=True)
class UserChargeTarget:
    user_id: int
    username: str
    owner_id: int | None
    attribute_name: str


@dataclass(frozen=True, slots=True)
class UserChargeAssignment:
    user_id: int
    username: str
    attribute_name: str
    charge_id: int | None
    charge_name: str | None


@dataclass(frozen=True, slots=True)
class UserChargeAssignmentRepository:
    conn: UserChargeConnection

    @staticmethod
    def _component(attribute_name: str) -> tuple[str, str, str]:
        if attribute_name == "normal_charge":
            return "normal_users", "normal_username", "Internet"
        if attribute_name == "voip_charge":
            return "voip_users", "voip_username", "VoIP"
        raise ValueError("attribute_name must be normal_charge or voip_charge")

    def lock_target(self, username: str, attribute_name: str) -> UserChargeTarget | None:
        table, username_column, _ = self._component(attribute_name)
        row = self.conn.execute(
            f"""
            SELECT u.user_id, u.owner_id, component.{username_column}
            FROM users u
            JOIN {table} component ON component.user_id = u.user_id
            WHERE component.{username_column} = %s
            FOR UPDATE OF u
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None
        return UserChargeTarget(
            user_id=int(row[0]), owner_id=int(row[1]) if row[1] is not None else None,
            username=str(row[2]), attribute_name=attribute_name,
        )

    def get(self, target: UserChargeTarget) -> UserChargeAssignment:
        row = self.conn.execute(
            "SELECT attr_value FROM user_attrs WHERE user_id=%s AND attr_name=%s",
            (target.user_id, target.attribute_name),
        ).fetchone()
        if row is None:
            return UserChargeAssignment(target.user_id, target.username, target.attribute_name, None, None)
        try:
            charge_id = int(row[0])
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"invalid stored {target.attribute_name} charge ID") from exc
        charge = self.conn.execute(
            "SELECT name FROM charges WHERE charge_id=%s", (charge_id,)
        ).fetchone()
        if charge is None:
            raise RuntimeError(f"{target.attribute_name} references missing charge {charge_id}")
        return UserChargeAssignment(
            target.user_id, target.username, target.attribute_name, charge_id, str(charge[0])
        )

    def assign(self, target: UserChargeTarget, *, admin_id: int, charge_name: str) -> UserChargeAssignment:
        charge = self.conn.execute(
            """SELECT charge_id, name, charge_type
               FROM charges WHERE name=%s FOR SHARE""",
            (charge_name,),
        ).fetchone()
        if charge is None:
            raise UserChargeNotFound(charge_name)
        if str(charge[2]) != self._component(target.attribute_name)[2]:
            raise UserChargeTypeError(charge_name)
        charge_id, resolved_name = int(charge[0]), str(charge[1])
        old = self.conn.execute(
            "SELECT attr_value FROM user_attrs WHERE user_id=%s AND attr_name=%s FOR UPDATE",
            (target.user_id, target.attribute_name),
        ).fetchone()
        old_value = str(old[0]) if old is not None else AUDIT_LOG_NOVALUE
        new_value = str(charge_id)
        if old_value != new_value:
            self.conn.execute(
                """INSERT INTO user_attrs (user_id, attr_name, attr_value)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, attr_name)
                   DO UPDATE SET attr_value=EXCLUDED.attr_value""",
                (target.user_id, target.attribute_name, new_value),
            )
            if is_user_audit_log_enabled(self.conn):
                old_name = self._charge_name(old_value)
                UserAttributeMutationRepository(self.conn)._audit(
                    admin_id, target.user_id, target.attribute_name,
                    old_name, resolved_name,
                )
        return UserChargeAssignment(
            target.user_id, target.username, target.attribute_name, charge_id, resolved_name
        )

    def delete(self, target: UserChargeTarget, *, admin_id: int) -> UserChargeAssignment:
        old = self.conn.execute(
            "SELECT attr_value FROM user_attrs WHERE user_id=%s AND attr_name=%s FOR UPDATE",
            (target.user_id, target.attribute_name),
        ).fetchone()
        old_id = None
        old_name = None
        if old is not None:
            try:
                old_id = int(old[0])
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"invalid stored {target.attribute_name} charge ID") from exc
            old_name = self._charge_name(str(old_id))
            self.conn.execute(
                "DELETE FROM user_attrs WHERE user_id=%s AND attr_name=%s",
                (target.user_id, target.attribute_name),
            )
            if is_user_audit_log_enabled(self.conn):
                UserAttributeMutationRepository(self.conn)._audit(
                    admin_id, target.user_id, target.attribute_name,
                    old_name, AUDIT_LOG_NOVALUE,
                )
        return UserChargeAssignment(
            target.user_id, target.username, target.attribute_name, None, None
        )

    def _charge_name(self, charge_id: str) -> str:
        if charge_id == AUDIT_LOG_NOVALUE:
            return AUDIT_LOG_NOVALUE
        try:
            numeric_id = int(charge_id)
        except ValueError as exc:
            raise RuntimeError("invalid stored charge ID") from exc
        row = self.conn.execute(
            "SELECT name FROM charges WHERE charge_id=%s", (numeric_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"charge {numeric_id} not found")
        return str(row[0])
