"""Native IBSng A1.24 charge catalog persistence."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


class ChargeConnection(Protocol):
    def execute(self, sql: str, params=()): ...


class ChargeNotFound(LookupError): pass
class ChargeAlreadyExists(ValueError): pass
class ChargeInputError(ValueError): pass
class ChargeInUseError(ValueError): pass


@dataclass(frozen=True, slots=True)
class ChargeRecord:
    charge_id: int
    name: str
    comment: str
    charge_type: str
    admin_id: int | None
    visible_to_all: bool


@dataclass(frozen=True, slots=True)
class PostgresChargeRepository:
    conn: ChargeConnection

    def list(self) -> list[ChargeRecord]:
        rows = self.conn.execute(
            """SELECT charge_id, name, comment, charge_type, admin_id, visible_to_all
               FROM charges ORDER BY name, charge_id"""
        ).fetchall()
        return [self._build(row) for row in rows]

    def get(self, charge_id: int) -> ChargeRecord | None:
        rows = self.conn.execute(
            """SELECT charge_id, name, comment, charge_type, admin_id, visible_to_all
               FROM charges WHERE charge_id=%s""",
            (charge_id,),
        ).fetchall()
        return self._build(rows[0]) if rows else None

    def get_by_name(self, name: str) -> ChargeRecord | None:
        rows = self.conn.execute(
            """SELECT charge_id, name, comment, charge_type, admin_id, visible_to_all
               FROM charges WHERE name=%s""",
            (name,),
        ).fetchall()
        return self._build(rows[0]) if rows else None

    def create(
        self, name: str, comment: str, charge_type: str,
        admin_id: int, visible_to_all: bool,
    ) -> int:
        self._validate(name, charge_type)
        if admin_id <= 0:
            raise ChargeInputError("admin_id must be positive")
        self.conn.execute("LOCK TABLE charges IN SHARE ROW EXCLUSIVE MODE")
        if self.conn.execute("SELECT charge_id FROM charges WHERE name=%s", (name,)).fetchone():
            raise ChargeAlreadyExists(name)
        charge_id = int(self.conn.execute("SELECT nextval('charges_id_seq')").fetchone()[0])
        self.conn.execute(
            """INSERT INTO charges
               (charge_id, name, comment, charge_type, admin_id, visible_to_all)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (charge_id, name, comment, charge_type, admin_id, visible_to_all),
        )
        return charge_id

    def update(self, charge_id: int, name: str, comment: str, visible_to_all: bool) -> None:
        self._validate(name, None)
        current = self.conn.execute(
            "SELECT charge_id FROM charges WHERE charge_id=%s FOR UPDATE", (charge_id,)
        ).fetchone()
        if current is None:
            raise ChargeNotFound(str(charge_id))
        duplicate = self.conn.execute(
            "SELECT charge_id FROM charges WHERE name=%s AND charge_id<>%s",
            (name, charge_id),
        ).fetchone()
        if duplicate is not None:
            raise ChargeAlreadyExists(name)
        self.conn.execute(
            "UPDATE charges SET name=%s, comment=%s, visible_to_all=%s WHERE charge_id=%s",
            (name, comment, visible_to_all, charge_id),
        )

    def delete(self, name: str) -> int:
        self.conn.execute("LOCK TABLE charges IN SHARE ROW EXCLUSIVE MODE")
        rows = self.conn.execute(
            """SELECT charge_id, charge_type FROM charges WHERE name=%s FOR UPDATE""",
            (name,),
        ).fetchall()
        if not rows:
            raise ChargeNotFound(name)
        charge_id, charge_type = int(rows[0][0]), str(rows[0][1])
        attr_name = "normal_charge" if charge_type == "Internet" else "voip_charge"
        user_rows = self.conn.execute(
            "SELECT user_id FROM user_attrs WHERE attr_name=%s AND attr_value=%s ORDER BY user_id",
            (attr_name, str(charge_id)),
        ).fetchall()
        group_rows = self.conn.execute(
            "SELECT group_id FROM group_attrs WHERE attr_name=%s AND attr_value=%s ORDER BY group_id",
            (attr_name, str(charge_id)),
        ).fetchall()
        if user_rows or group_rows:
            raise ChargeInUseError(
                f"charge is assigned to users={','.join(str(row[0]) for row in user_rows)} "
                f"groups={','.join(str(row[0]) for row in group_rows)}"
            )
        rule_rows = self.conn.execute(
            "SELECT charge_rule_id FROM charge_rules WHERE charge_id=%s ORDER BY charge_rule_id",
            (charge_id,),
        ).fetchall()
        table = "internet_charge_rules" if charge_type == "Internet" else "voip_charge_rules"
        for rule in rule_rows:
            rule_id = int(rule[0])
            self.conn.execute("DELETE FROM charge_rule_ports WHERE charge_rule_id=%s", (rule_id,))
            self.conn.execute("DELETE FROM charge_rule_day_of_weeks WHERE charge_rule_id=%s", (rule_id,))
            self.conn.execute(f"DELETE FROM {table} WHERE charge_rule_id=%s", (rule_id,))
        self.conn.execute("DELETE FROM charges WHERE charge_id=%s", (charge_id,))
        return charge_id

    @staticmethod
    def _validate(name: str, charge_type: str | None) -> None:
        if not name or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ChargeInputError("invalid A1.24 charge name")
        if charge_type is not None and charge_type not in {"Internet", "VoIP"}:
            raise ChargeInputError("charge_type must be Internet or VoIP")

    @staticmethod
    def _build(row) -> ChargeRecord:
        return ChargeRecord(
            charge_id=int(row[0]), name=str(row[1]), comment=str(row[2] or ""),
            charge_type=str(row[3]), admin_id=int(row[4]) if row[4] is not None else None,
            visible_to_all=bool(row[5]),
        )
