"""Read-only access to native A1.24 bandwidth-manager leaves."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class BandwidthManagerConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class BandwidthLeaf:
    leaf_id: int
    leaf_name: str
    interface_id: int | None
    parent_id: int | None
    default_rate_kbits: int | None
    default_ceil_kbits: int | None
    total_rate_kbits: int | None
    total_ceil_kbits: int | None


@dataclass(frozen=True, slots=True)
class PostgresBandwidthLeafRepository:
    conn: BandwidthManagerConnection

    def list(self) -> list[BandwidthLeaf]:
        rows = self.conn.execute(
            """
            SELECT leaf_id, leaf_name, interface_id, parent_id,
                   default_rate_kbits, default_ceil_kbits,
                   total_rate_kbits, total_ceil_kbits
            FROM bw_leaf
            ORDER BY leaf_name, leaf_id
            """
        ).fetchall()
        return [self._build(row) for row in rows]

    def get_by_name(self, leaf_name: str) -> BandwidthLeaf | None:
        rows = self.conn.execute(
            """
            SELECT leaf_id, leaf_name, interface_id, parent_id,
                   default_rate_kbits, default_ceil_kbits,
                   total_rate_kbits, total_ceil_kbits
            FROM bw_leaf
            WHERE leaf_name = %s
            ORDER BY leaf_id
            LIMIT 1
            """,
            (leaf_name,),
        ).fetchall()
        return self._build(rows[0]) if rows else None

    @staticmethod
    def _build(row) -> BandwidthLeaf:
        return BandwidthLeaf(
            leaf_id=int(row[0]),
            leaf_name=str(row[1]),
            interface_id=int(row[2]) if row[2] is not None else None,
            parent_id=int(row[3]) if row[3] is not None else None,
            default_rate_kbits=int(row[4]) if row[4] is not None else None,
            default_ceil_kbits=int(row[5]) if row[5] is not None else None,
            total_rate_kbits=int(row[6]) if row[6] is not None else None,
            total_ceil_kbits=int(row[7]) if row[7] is not None else None,
        )
