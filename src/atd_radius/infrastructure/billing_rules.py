"""Native A1.24 PostgreSQL charge-rule repository."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from atd_radius.domain.billing_rules import ALL, InternetChargeRule


class ChargeRuleConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class PostgresInternetChargeRuleRepository:
    conn: ChargeRuleConnection

    def list(self, charge_id: int | None = None) -> list[InternetChargeRule]:
        where = ""
        params: tuple[object, ...] = ()
        if charge_id is not None:
            where = " WHERE charge_id=%s"
            params = (charge_id,)
        rows = self.conn.execute(
            """
            SELECT charge_rule_id, start_time, end_time, ras_id,
                   cpm, cpk, assumed_kps, bandwidth_limit_kbytes
            FROM internet_charge_rules
            """
            + where
            + " ORDER BY charge_rule_id",
            params,
        ).fetchall()
        result = []
        for row in rows:
            rule_id = int(row[0])
            ports = self._ports(rule_id)
            days = self._days(rule_id)
            result.append(
                InternetChargeRule(
                    rule_id=rule_id,
                    days=frozenset(days),
                    start_second=self._seconds(row[1]),
                    end_second=self._seconds(row[2]),
                    ras_id=int(row[3]) if row[3] is not None else None,
                    ports=frozenset(ports),
                    cpm=Decimal(str(row[4])),
                    cpk=Decimal(str(row[5])),
                    assumed_kps=int(row[6] or 0),
                    bandwidth_limit_kbytes=int(row[7] if row[7] is not None else -1),
                )
            )
        return result

    def get(self, rule_id: int) -> InternetChargeRule | None:
        rows = self.conn.execute(
            """
            SELECT charge_rule_id, start_time, end_time, ras_id,
                   cpm, cpk, assumed_kps, bandwidth_limit_kbytes
            FROM internet_charge_rules
            WHERE charge_rule_id=%s
            """,
            (rule_id,),
        ).fetchall()
        if not rows:
            return None
        row = rows[0]
        return self._build(row)

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
        )

    def _days(self, rule_id: int) -> list[int]:
        rows = self.conn.execute(
            "SELECT day_of_week FROM charge_rule_day_of_weeks WHERE charge_rule_id=%s ORDER BY day_of_week",
            (rule_id,),
        ).fetchall()
        return [int(row[0]) for row in rows]

    def _ports(self, rule_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT ras_port FROM charge_rule_ports WHERE charge_rule_id=%s ORDER BY ras_port",
            (rule_id,),
        ).fetchall()
        return [str(row[0]) for row in rows]

    @staticmethod
    def _seconds(value) -> int:
        if hasattr(value, "hour"):
            return value.hour * 3600 + value.minute * 60 + value.second
        text = str(value)
        parts = text.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
