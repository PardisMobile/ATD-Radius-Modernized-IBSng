"""Read native IBSng A1.24 VoIP charge rules from the inherited PostgreSQL table."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from atd_radius.domain.billing_rules import VoipChargeRule


class VoipChargeRuleConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class PostgresVoipChargeRuleRepository:
    conn: VoipChargeRuleConnection

    def list(self, charge_id: int | None = None) -> list[VoipChargeRule]:
        where = ""
        params: tuple[object, ...] = ()
        if charge_id is not None:
            where = " WHERE charge_id = %s"
            params = (charge_id,)
        rows = self.conn.execute(
            """
            SELECT charge_rule_id, charge_id, start_time, end_time,
                   time_limit, ras_id, tariff_id
            FROM voip_charge_rules
            """
            + where
            + " ORDER BY charge_rule_id",
            params,
        ).fetchall()
        return [self._build(row) for row in rows]

    def get(self, rule_id: int) -> VoipChargeRule | None:
        rows = self.conn.execute(
            """
            SELECT charge_rule_id, charge_id, start_time, end_time,
                   time_limit, ras_id, tariff_id
            FROM voip_charge_rules
            WHERE charge_rule_id = %s
            """,
            (rule_id,),
        ).fetchall()
        return self._build(rows[0]) if rows else None

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
            rule_id=rule_id,
            days=frozenset(int(item[0]) for item in days),
            start_second=self._seconds(row[2]),
            end_second=self._seconds(row[3]),
            ras_id=int(row[5]) if row[5] is not None else None,
            ports=frozenset(str(item[0]) for item in ports),
            charge_id=int(row[1]),
            tariff_id=int(row[6]),
            time_limit=int(row[4]) if row[4] is not None else None,
        )

    @staticmethod
    def _seconds(value) -> int:
        if hasattr(value, "hour"):
            return value.hour * 3600 + value.minute * 60 + value.second
        parts = str(value).split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(Decimal(parts[2]))
