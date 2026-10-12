"""Source-shaped PostgreSQL persistence for A1.24 VoIP charge rules."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from atd_radius.domain.billing_rules import ALL, VoipChargeRule


class VoipChargeRuleConnection(Protocol):
    def execute(self, sql: str, params=()): ...


class VoipRuleNotFound(LookupError): pass
class VoipRuleInputError(ValueError): pass
class VoipRuleConflictError(ValueError): pass
class ChargeNotFound(LookupError): pass
class ChargeTypeError(ValueError): pass
class VoipTariffNotFound(LookupError): pass


@dataclass(frozen=True, slots=True)
class VoipChargeRuleInput:
    start_time: str
    end_time: str
    days: tuple[str, ...]
    tariff_name: str
    ras_id: int | None
    ports: tuple[str, ...]


_DAYS = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
    "Friday": 4, "Saturday": 5, "Sunday": 6,
}


@dataclass(frozen=True, slots=True)
class PostgresVoipChargeRuleRepository:
    conn: VoipChargeRuleConnection

    def list(self, charge_id: int | None = None) -> list[VoipChargeRule]:
        where, params = ("", ()) if charge_id is None else (" WHERE charge_id = %s", (charge_id,))
        rows = self.conn.execute(
            """
            SELECT charge_rule_id, charge_id, start_time, end_time,
                   time_limit, ras_id, tariff_id
            FROM voip_charge_rules
            """ + where + " ORDER BY charge_rule_id", params,
        ).fetchall()
        return [self._build(row) for row in rows]

    def get(self, rule_id: int) -> VoipChargeRule | None:
        rows = self.conn.execute(
            """SELECT charge_rule_id, charge_id, start_time, end_time,
                      time_limit, ras_id, tariff_id
               FROM voip_charge_rules WHERE charge_rule_id = %s""",
            (rule_id,),
        ).fetchall()
        return self._build(rows[0]) if rows else None

    def create(self, charge_name: str, payload: VoipChargeRuleInput) -> int:
        charge_id = self._require_voip_charge(charge_name)
        tariff_id = self._require_tariff(payload.tariff_name)
        normalized = self._validate(payload)
        self._require_ras_ports(payload.ras_id, payload.ports)
        self._check_conflict(charge_id, normalized, payload.ras_id)
        rule_id = int(self.conn.execute(
            "SELECT nextval('charge_rules_id_seq')"
        ).fetchone()[0])
        self.conn.execute(
            """INSERT INTO voip_charge_rules
               (charge_id, charge_rule_id, start_time, end_time, tariff_id, ras_id)
               VALUES (%s, %s, %s::time, %s::time, %s, %s)""",
            (charge_id, rule_id, normalized[0], normalized[1], tariff_id, payload.ras_id),
        )
        self._insert_days_and_ports(rule_id, normalized[2], normalized[3])
        return rule_id

    def update(self, charge_name: str, rule_id: int, payload: VoipChargeRuleInput) -> None:
        charge_id = self._require_voip_charge(charge_name)
        row = self.conn.execute(
            """SELECT charge_rule_id FROM voip_charge_rules
               WHERE charge_rule_id = %s AND charge_id = %s FOR UPDATE""",
            (rule_id, charge_id),
        ).fetchone()
        if row is None:
            raise VoipRuleNotFound(str(rule_id))
        tariff_id = self._require_tariff(payload.tariff_name)
        normalized = self._validate(payload)
        self._require_ras_ports(payload.ras_id, payload.ports)
        self._check_conflict(charge_id, normalized, payload.ras_id, ignore_rule_id=rule_id)
        self.conn.execute(
            """UPDATE voip_charge_rules
               SET start_time = %s::time, end_time = %s::time, tariff_id = %s, ras_id = %s
               WHERE charge_rule_id = %s AND charge_id = %s""",
            (normalized[0], normalized[1], tariff_id, payload.ras_id, rule_id, charge_id),
        )
        self.conn.execute("DELETE FROM charge_rule_ports WHERE charge_rule_id = %s", (rule_id,))
        self.conn.execute("DELETE FROM charge_rule_day_of_weeks WHERE charge_rule_id = %s", (rule_id,))
        self._insert_days_and_ports(rule_id, normalized[2], normalized[3])

    def delete(self, charge_name: str, rule_id: int) -> None:
        charge_id = self._require_voip_charge(charge_name)
        row = self.conn.execute(
            """SELECT charge_rule_id FROM voip_charge_rules
               WHERE charge_rule_id = %s AND charge_id = %s FOR UPDATE""",
            (rule_id, charge_id),
        ).fetchone()
        if row is None:
            raise VoipRuleNotFound(str(rule_id))
        self.conn.execute("DELETE FROM charge_rule_ports WHERE charge_rule_id = %s", (rule_id,))
        self.conn.execute("DELETE FROM charge_rule_day_of_weeks WHERE charge_rule_id = %s", (rule_id,))
        self.conn.execute(
            "DELETE FROM voip_charge_rules WHERE charge_rule_id = %s AND charge_id = %s",
            (rule_id, charge_id),
        )

    def _require_voip_charge(self, charge_name: str) -> int:
        rows = self.conn.execute(
            "SELECT charge_id, charge_type FROM charges WHERE name = %s", (charge_name,)
        ).fetchall()
        if not rows:
            raise ChargeNotFound(charge_name)
        if str(rows[0][1]) != "VoIP":
            raise ChargeTypeError(charge_name)
        return int(rows[0][0])

    def _require_ras_ports(self, ras_id: int | None, ports: tuple[str, ...]) -> None:
        if ras_id is None:
            return
        rows = self.conn.execute(
            "SELECT ras_id FROM ras WHERE ras_id = %s", (ras_id,)
        ).fetchall()
        if not rows:
            raise VoipRuleInputError(f"RAS ID does not exist: {ras_id}")
        if ALL in ports:
            return
        configured = {
            str(row[0])
            for row in self.conn.execute(
                "SELECT port_name FROM ras_ports WHERE ras_id = %s AND port_name = ANY(%s)",
                (ras_id, list(ports)),
            ).fetchall()
        }
        if configured != set(ports):
            missing = sorted(set(ports) - configured)
            raise VoipRuleInputError(
                f"port(s) not configured on RAS {ras_id}: {', '.join(missing)}"
            )

    def _require_tariff(self, tariff_name: str) -> int:
        rows = self.conn.execute(
            "SELECT tariff_id FROM voip_charge_rule_tariff WHERE tariff_name = %s", (tariff_name,)
        ).fetchall()
        if not rows:
            raise VoipTariffNotFound(tariff_name)
        return int(rows[0][0])

    def _validate(self, payload: VoipChargeRuleInput) -> tuple[str, str, frozenset[int], tuple[str | None, ...]]:
        start, end = self._parse_time(payload.start_time), self._parse_time(payload.end_time)
        if start >= end:
            raise VoipRuleInputError("end time must be later than start time")
        if not payload.days:
            raise VoipRuleInputError("at least one day is required")
        try:
            days = frozenset(_DAYS[day] for day in payload.days)
        except KeyError as exc:
            raise VoipRuleInputError(f"invalid day of week: {exc.args[0]}") from exc
        if len(days) != len(payload.days):
            raise VoipRuleInputError("duplicate days are not allowed")
        if payload.ras_id is not None:
            if payload.ras_id <= 0:
                raise VoipRuleInputError("RAS ID must be positive or omitted for all RASes")
            if not payload.ports:
                raise VoipRuleInputError("a RAS-specific rule requires at least one port")
        if len(set(payload.ports)) != len(payload.ports):
            raise VoipRuleInputError("duplicate ports are not allowed")
        if any(not port for port in payload.ports):
            raise VoipRuleInputError("port names cannot be empty")
        if ALL in payload.ports and len(payload.ports) > 1:
            raise VoipRuleInputError("_ALL_ cannot be combined with named ports")
        # A1.24 inserts one NULL ras_port row when the submitted port list is
        # empty. Preserve that DB shape; it is not a wildcard at runtime.
        normalized_ports: tuple[str | None, ...] = tuple(payload.ports) if payload.ports else (None,)
        return start, end, days, normalized_ports

    @staticmethod
    def _parse_time(value: str) -> str:
        match = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?", value)
        if not match:
            raise VoipRuleInputError("invalid time format")
        hour, minute, second = int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0)
        if hour == 24:
            return "23:59:59"
        if hour > 23 or minute > 59 or second > 59:
            raise VoipRuleInputError("time out of range")
        return f"{hour:02d}:{minute:02d}:{second:02d}"

    def _check_conflict(
        self, charge_id: int, normalized: tuple[str, str, frozenset[int], tuple[str | None, ...]],
        ras_id: int | None, *, ignore_rule_id: int | None = None,
    ) -> None:
        start, end, days, ports = normalized
        # Preserve A1.24 ChargeRule.hasOverlap: only equal RAS IDs and literal
        # port intersections are compared; wildcard-vs-specific is not widened.
        rows = self.conn.execute(
            """SELECT charge_rule_id, start_time, end_time, ras_id
               FROM voip_charge_rules WHERE charge_id = %s ORDER BY charge_rule_id""",
            (charge_id,),
        ).fetchall()
        for row in rows:
            other_id = int(row[0])
            if other_id == ignore_rule_id:
                continue
            other_ras = int(row[3]) if row[3] is not None else None
            if other_ras != ras_id:
                continue
            other_ports = {
                item[0] if item[0] is None else str(item[0])
                for item in self.conn.execute(
                    "SELECT ras_port FROM charge_rule_ports WHERE charge_rule_id = %s",
                    (other_id,),
                ).fetchall()
            }
            if not set(ports).intersection(other_ports):
                continue
            other_days = {int(item[0]) for item in self.conn.execute(
                "SELECT day_of_week FROM charge_rule_day_of_weeks WHERE charge_rule_id = %s", (other_id,)
            ).fetchall()}
            if not days.intersection(other_days):
                continue
            other_start, other_end = self._seconds(row[1]), self._seconds(row[2])
            start_sec, end_sec = self._seconds(start), self._seconds(end)
            if max(start_sec, other_start) < min(end_sec, other_end):
                raise VoipRuleConflictError(f"rule overlaps with existing rule {other_id}")

    @staticmethod
    def _seconds(value) -> int:
        if hasattr(value, "hour"):
            return value.hour * 3600 + value.minute * 60 + value.second
        parts = str(value).split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(Decimal(parts[2]))

    def _insert_days_and_ports(
        self, rule_id: int, days: frozenset[int], ports: tuple[str | None, ...]
    ) -> None:
        for day in sorted(days):
            self.conn.execute(
                "INSERT INTO charge_rule_day_of_weeks (charge_rule_id, day_of_week) VALUES (%s, %s)",
                (rule_id, day),
            )
        for port in ports:
            self.conn.execute(
                "INSERT INTO charge_rule_ports (charge_rule_id, ras_port) VALUES (%s, %s)",
                (rule_id, port),
            )

    def _build(self, row) -> VoipChargeRule:
        rule_id = int(row[0])
        days = self.conn.execute(
            "SELECT day_of_week FROM charge_rule_day_of_weeks WHERE charge_rule_id = %s ORDER BY day_of_week",
            (rule_id,),
        ).fetchall()
        ports = self.conn.execute(
            "SELECT ras_port FROM charge_rule_ports WHERE charge_rule_id = %s ORDER BY ras_port",
            (rule_id,),
        ).fetchall()
        return VoipChargeRule(
            rule_id=rule_id, days=frozenset(int(item[0]) for item in days),
            start_second=self._seconds(row[2]), end_second=self._seconds(row[3]),
            ras_id=int(row[5]) if row[5] is not None else None,
            ports=frozenset(item[0] if item[0] is None else str(item[0]) for item in ports),
            charge_id=int(row[1]), tariff_id=int(row[6]),
            time_limit=int(row[4]) if row[4] is not None else None,
        )
