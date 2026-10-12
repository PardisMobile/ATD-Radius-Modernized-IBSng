"""Native A1.24 PostgreSQL repository for Internet charge-rule CRUD."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from atd_radius.domain.billing_rules import ALL, InternetChargeRule


class ChargeRuleConnection(Protocol):
    def execute(self, sql: str, params=()): ...


class InternetChargeNotFound(LookupError): pass
class InternetChargeTypeError(ValueError): pass
class InternetRuleNotFound(LookupError): pass
class InternetRuleInputError(ValueError): pass
class InternetRuleConflictError(ValueError): pass


@dataclass(frozen=True, slots=True)
class InternetChargeRuleInput:
    start_time: str
    end_time: str
    days: tuple[str, ...]
    cpm: Decimal
    cpk: Decimal
    assumed_kps: int
    bandwidth_limit_kbytes: int
    tx_leaf_name: str
    rx_leaf_name: str
    ras_id: int | None
    ports: tuple[str, ...]


_DAYS = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
    "Friday": 4, "Saturday": 5, "Sunday": 6,
}


@dataclass(frozen=True, slots=True)
class PostgresInternetChargeRuleRepository:
    conn: ChargeRuleConnection

    _SELECT = """
        SELECT charge_rule_id, start_time, end_time, ras_id,
               cpm, cpk, assumed_kps, bandwidth_limit_kbytes,
               bw_transmit_leaf_id, bw_receive_leaf_id, charge_id
        FROM internet_charge_rules
    """

    def list(self, charge_id: int | None = None) -> list[InternetChargeRule]:
        where, params = ("", ()) if charge_id is None else (" WHERE charge_id=%s", (charge_id,))
        rows = self.conn.execute(self._SELECT + where + " ORDER BY charge_rule_id", params).fetchall()
        return [self._build(row) for row in rows]

    def get(self, rule_id: int) -> InternetChargeRule | None:
        rows = self.conn.execute(
            self._SELECT + " WHERE charge_rule_id=%s", (rule_id,)
        ).fetchall()
        return self._build(rows[0]) if rows else None

    def create(self, charge_name: str, payload: InternetChargeRuleInput) -> int:
        charge_id = self._require_internet_charge(charge_name)
        tx_leaf_id, rx_leaf_id = self._require_leaf_pair(payload.tx_leaf_name, payload.rx_leaf_name)
        normalized = self._validate(payload)
        self._require_ras_ports(payload.ras_id, payload.ports)
        self._check_conflict(charge_id, normalized, payload.ras_id)
        rule_id = int(self.conn.execute("SELECT nextval('charge_rules_id_seq')").fetchone()[0])
        self.conn.execute(
            """
            INSERT INTO internet_charge_rules
              (charge_id, charge_rule_id, start_time, end_time, cpm, cpk,
               assumed_kps, bandwidth_limit_kbytes, bw_transmit_leaf_id,
               bw_receive_leaf_id, ras_id)
            VALUES (%s, %s, %s::time, %s::time, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                charge_id, rule_id, normalized[0], normalized[1], payload.cpm,
                payload.cpk, payload.assumed_kps, payload.bandwidth_limit_kbytes,
                tx_leaf_id, rx_leaf_id, payload.ras_id,
            ),
        )
        self._insert_days_and_ports(rule_id, normalized[2], normalized[3])
        return rule_id

    def update(self, charge_name: str, rule_id: int, payload: InternetChargeRuleInput) -> None:
        charge_id = self._require_internet_charge(charge_name)
        existing = self.conn.execute(
            """SELECT charge_rule_id FROM internet_charge_rules
               WHERE charge_rule_id=%s AND charge_id=%s FOR UPDATE""",
            (rule_id, charge_id),
        ).fetchone()
        if existing is None:
            raise InternetRuleNotFound(str(rule_id))
        tx_leaf_id, rx_leaf_id = self._require_leaf_pair(payload.tx_leaf_name, payload.rx_leaf_name)
        normalized = self._validate(payload)
        self._require_ras_ports(payload.ras_id, payload.ports)
        self._check_conflict(charge_id, normalized, payload.ras_id, ignore_rule_id=rule_id)
        self.conn.execute(
            """
            UPDATE internet_charge_rules
            SET start_time=%s::time, end_time=%s::time, cpm=%s, cpk=%s,
                assumed_kps=%s, bandwidth_limit_kbytes=%s,
                bw_transmit_leaf_id=%s, bw_receive_leaf_id=%s, ras_id=%s
            WHERE charge_rule_id=%s AND charge_id=%s
            """,
            (
                normalized[0], normalized[1], payload.cpm, payload.cpk,
                payload.assumed_kps, payload.bandwidth_limit_kbytes,
                tx_leaf_id, rx_leaf_id, payload.ras_id, rule_id, charge_id,
            ),
        )
        self.conn.execute("DELETE FROM charge_rule_ports WHERE charge_rule_id=%s", (rule_id,))
        self.conn.execute("DELETE FROM charge_rule_day_of_weeks WHERE charge_rule_id=%s", (rule_id,))
        self._insert_days_and_ports(rule_id, normalized[2], normalized[3])

    def delete(self, charge_name: str, rule_id: int) -> None:
        charge_id = self._require_internet_charge(charge_name)
        row = self.conn.execute(
            """SELECT charge_rule_id FROM internet_charge_rules
               WHERE charge_rule_id=%s AND charge_id=%s FOR UPDATE""",
            (rule_id, charge_id),
        ).fetchone()
        if row is None:
            raise InternetRuleNotFound(str(rule_id))
        self.conn.execute("DELETE FROM charge_rule_ports WHERE charge_rule_id=%s", (rule_id,))
        self.conn.execute("DELETE FROM charge_rule_day_of_weeks WHERE charge_rule_id=%s", (rule_id,))
        self.conn.execute(
            "DELETE FROM internet_charge_rules WHERE charge_rule_id=%s AND charge_id=%s",
            (rule_id, charge_id),
        )

    def _require_internet_charge(self, charge_name: str) -> int:
        rows = self.conn.execute(
            "SELECT charge_id, charge_type FROM charges WHERE name=%s", (charge_name,)
        ).fetchall()
        if not rows:
            raise InternetChargeNotFound(charge_name)
        if str(rows[0][1]) != "Internet":
            raise InternetChargeTypeError(charge_name)
        return int(rows[0][0])

    def _require_leaf_pair(self, tx_name: str, rx_name: str) -> tuple[int | None, int | None]:
        if bool(tx_name) != bool(rx_name):
            raise InternetRuleInputError("transmit and receive bandwidth leaf names must both be set")
        if not tx_name:
            return None, None
        ids = []
        for name in (tx_name, rx_name):
            rows = self.conn.execute(
                "SELECT leaf_id FROM bw_leaf WHERE leaf_name=%s ORDER BY leaf_id LIMIT 1",
                (name,),
            ).fetchall()
            if not rows:
                raise InternetRuleInputError(f"bandwidth leaf does not exist: {name}")
            ids.append(int(rows[0][0]))
        return ids[0], ids[1]

    def _validate(self, payload: InternetChargeRuleInput) -> tuple[str, str, frozenset[int], tuple[str | None, ...]]:
        start, end = self._parse_time(payload.start_time), self._parse_time(payload.end_time)
        if start >= end:
            raise InternetRuleInputError("end time must be later than start time")
        if not payload.days:
            raise InternetRuleInputError("at least one day is required")
        try:
            days = frozenset(_DAYS[day] for day in payload.days)
        except KeyError as exc:
            raise InternetRuleInputError(f"invalid day of week: {exc.args[0]}") from exc
        if len(days) != len(payload.days):
            raise InternetRuleInputError("duplicate days are not allowed")
        if payload.assumed_kps <= 0:
            raise InternetRuleInputError("assumed_kps must be positive")
        if payload.bandwidth_limit_kbytes < 0:
            raise InternetRuleInputError("bandwidth_limit_kbytes cannot be negative")
        if payload.cpm < 0 or payload.cpk < 0:
            raise InternetRuleInputError("cpm and cpk cannot be negative")
        if payload.ras_id is not None:
            if payload.ras_id <= 0:
                raise InternetRuleInputError("RAS ID must be positive or omitted for all RASes")
            if not payload.ports:
                raise InternetRuleInputError("a RAS-specific rule requires at least one port")
        if len(set(payload.ports)) != len(payload.ports):
            raise InternetRuleInputError("duplicate ports are not allowed")
        if any(not port for port in payload.ports):
            raise InternetRuleInputError("port names cannot be empty")
        if ALL in payload.ports and len(payload.ports) > 1:
            raise InternetRuleInputError("_ALL_ cannot be combined with named ports")
        normalized_ports: tuple[str | None, ...] = tuple(payload.ports) if payload.ports else (None,)
        return start, end, days, normalized_ports

    @staticmethod
    def _parse_time(value: str) -> str:
        match = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?", value)
        if not match:
            raise InternetRuleInputError("invalid time format")
        hour, minute, second = int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0)
        if hour == 24:
            return "23:59:59"
        if hour > 23 or minute > 59 or second > 59:
            raise InternetRuleInputError("time out of range")
        return f"{hour:02d}:{minute:02d}:{second:02d}"

    def _require_ras_ports(self, ras_id: int | None, ports: tuple[str, ...]) -> None:
        if ras_id is None:
            return
        rows = self.conn.execute("SELECT ras_id FROM ras WHERE ras_id=%s", (ras_id,)).fetchall()
        if not rows:
            raise InternetRuleInputError(f"RAS ID does not exist: {ras_id}")
        if ALL in ports:
            return
        configured = {
            str(row[0]) for row in self.conn.execute(
                "SELECT port_name FROM ras_ports WHERE ras_id=%s AND port_name = ANY(%s)",
                (ras_id, list(ports)),
            ).fetchall()
        }
        if configured != set(ports):
            raise InternetRuleInputError(f"port(s) not configured on RAS {ras_id}")

    def _check_conflict(
        self, charge_id: int, normalized: tuple[str, str, frozenset[int], tuple[str | None, ...]],
        ras_id: int | None, *, ignore_rule_id: int | None = None,
    ) -> None:
        start, end, days, ports = normalized
        rows = self.conn.execute(
            """SELECT charge_rule_id, start_time, end_time, ras_id
               FROM internet_charge_rules WHERE charge_id=%s ORDER BY charge_rule_id""",
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
                    "SELECT ras_port FROM charge_rule_ports WHERE charge_rule_id=%s", (other_id,)
                ).fetchall()
            }
            if not set(ports).intersection(other_ports):
                continue
            other_days = {
                int(item[0]) for item in self.conn.execute(
                    "SELECT day_of_week FROM charge_rule_day_of_weeks WHERE charge_rule_id=%s", (other_id,)
                ).fetchall()
            }
            if not days.intersection(other_days):
                continue
            other_start, other_end = self._seconds(row[1]), self._seconds(row[2])
            start_sec, end_sec = self._seconds(start), self._seconds(end)
            if max(start_sec, other_start) < min(end_sec, other_end):
                raise InternetRuleConflictError(f"rule overlaps with existing rule {other_id}")

    def _insert_days_and_ports(self, rule_id: int, days: frozenset[int], ports: tuple[str | None, ...]) -> None:
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

    def _days(self, rule_id: int) -> list[int]:
        rows = self.conn.execute(
            "SELECT day_of_week FROM charge_rule_day_of_weeks WHERE charge_rule_id=%s ORDER BY day_of_week",
            (rule_id,),
        ).fetchall()
        return [int(row[0]) for row in rows]

    def _ports(self, rule_id: int) -> list[str | None]:
        rows = self.conn.execute(
            "SELECT ras_port FROM charge_rule_ports WHERE charge_rule_id=%s ORDER BY ras_port",
            (rule_id,),
        ).fetchall()
        return [row[0] if row[0] is None else str(row[0]) for row in rows]

    def _build(self, row) -> InternetChargeRule:
        rule_id = int(row[0])
        return InternetChargeRule(
            rule_id=rule_id,
            days=frozenset(self._days(rule_id)),
            start_second=self._seconds(row[1]),
            end_second=self._seconds(row[2]),
            ras_id=int(row[3]) if row[3] is not None else None,
            ports=frozenset(self._ports(rule_id)),
            cpm=Decimal(str(row[4])),
            cpk=Decimal(str(row[5])),
            assumed_kps=int(row[6] or 0),
            bandwidth_limit_kbytes=int(row[7] if row[7] is not None else -1),
            bw_transmit_leaf_id=int(row[8]) if row[8] is not None else None,
            bw_receive_leaf_id=int(row[9]) if row[9] is not None else None,
            charge_id=int(row[10]),
        )

    @staticmethod
    def _seconds(value) -> int:
        if hasattr(value, "hour"):
            return value.hour * 3600 + value.minute * 60 + value.second
        parts = str(value).split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(Decimal(parts[2]))
