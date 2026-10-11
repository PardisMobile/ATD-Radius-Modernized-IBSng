"""Read-only mapping for native IBSng A1.24 VoIP tariffs and prefixes."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from atd_radius.domain.voip_tariff import VoipPrefix, VoipTariff


class VoipTariffConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class PostgresVoipTariffRepository:
    """Load tariff data from A1.24 tables without inventing replacement schema."""

    conn: VoipTariffConnection

    def get(self, tariff_id: int) -> VoipTariff | None:
        rows = self.conn.execute(
            """
            SELECT tariff_id, tariff_name, comment
            FROM voip_charge_rule_tariff
            WHERE tariff_id = %s
            """,
            (tariff_id,),
        ).fetchall()
        if not rows:
            return None
        return self._build(rows[0])

    def get_by_name(self, tariff_name: str) -> VoipTariff | None:
        rows = self.conn.execute(
            """
            SELECT tariff_id, tariff_name, comment
            FROM voip_charge_rule_tariff
            WHERE tariff_name = %s
            """,
            (tariff_name,),
        ).fetchall()
        if not rows:
            return None
        return self._build(rows[0])

    def list(self) -> list[VoipTariff]:
        rows = self.conn.execute(
            """
            SELECT tariff_id, tariff_name, comment
            FROM voip_charge_rule_tariff
            ORDER BY tariff_id
            """
        ).fetchall()
        return [self._build(row) for row in rows]

    def _build(self, row) -> VoipTariff:
        tariff_id = int(row[0])
        prefix_rows = self.conn.execute(
            """
            SELECT prefix_id, prefix_code, prefix_name, cpm, free_seconds,
                   min_duration, round_to, min_chargable_duration
            FROM tariff_prefix_list
            WHERE tariff_id = %s
            """,
            (tariff_id,),
        ).fetchall()
        prefixes = tuple(
            VoipPrefix(
                prefix_id=int(prefix[0]),
                code=str(prefix[1]),
                name=str(prefix[2]),
                cpm=Decimal(str(prefix[3])),
                free_seconds=int(prefix[4]),
                min_duration=int(prefix[5]),
                round_to=int(prefix[6]),
                min_chargeable_duration=int(prefix[7]),
            )
            for prefix in prefix_rows
        )
        return VoipTariff(
            tariff_id=tariff_id,
            name=str(row[1]),
            comment=str(row[2] or ""),
            prefixes=prefixes,
        )
