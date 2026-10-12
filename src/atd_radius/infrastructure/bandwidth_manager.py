"""Read-only access to native A1.24 bandwidth-manager records and hierarchy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class BandwidthManagerConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class BandwidthInterface:
    interface_id: int
    interface_name: str
    comment: str


@dataclass(frozen=True, slots=True)
class BandwidthNode:
    node_id: int
    interface_id: int
    parent_id: int | None
    rate_kbits: int | None
    ceil_kbits: int | None


@dataclass(frozen=True, slots=True)
class BandwidthTree:
    node_id: int
    children: tuple[BandwidthTree, ...]
    leaves: tuple[str, ...]


class BandwidthTreeCorruptError(ValueError):
    """Raised when persisted parent links form a cycle."""


@dataclass(frozen=True, slots=True)
class PostgresBandwidthManagerRepository:
    conn: BandwidthManagerConnection

    def list_interfaces(self) -> list[BandwidthInterface]:
        rows = self.conn.execute(
            """SELECT interface_id, interface_name, comment
               FROM bw_interface ORDER BY interface_name, interface_id"""
        ).fetchall()
        return [self._build_interface(row) for row in rows]

    def get_interface_by_name(self, interface_name: str) -> BandwidthInterface | None:
        rows = self.conn.execute(
            """SELECT interface_id, interface_name, comment
               FROM bw_interface WHERE interface_name = %s
               ORDER BY interface_id LIMIT 1""",
            (interface_name,),
        ).fetchall()
        return self._build_interface(rows[0]) if rows else None

    def get_node(self, node_id: int) -> BandwidthNode | None:
        rows = self.conn.execute(
            """SELECT node_id, interface_id, parent_id, rate_kbits, ceil_kbits
               FROM bw_node WHERE node_id = %s""",
            (node_id,),
        ).fetchall()
        return self._build_node(rows[0]) if rows else None

    def get_tree(self, interface_id: int) -> BandwidthTree | None:
        row = self.conn.execute(
            """SELECT node_id FROM bw_node
               WHERE interface_id = %s AND parent_id IS NULL
               ORDER BY node_id LIMIT 1""",
            (interface_id,),
        ).fetchone()
        if row is None:
            return None
        return self._build_subtree(int(row[0]), frozenset())

    def _build_subtree(self, node_id: int, ancestors: frozenset[int]) -> BandwidthTree:
        if node_id in ancestors:
            raise BandwidthTreeCorruptError(f"cycle detected at bandwidth node {node_id}")
        next_ancestors = ancestors | {node_id}
        child_rows = self.conn.execute(
            "SELECT node_id FROM bw_node WHERE parent_id = %s ORDER BY node_id",
            (node_id,),
        ).fetchall()
        leaf_rows = self.conn.execute(
            "SELECT leaf_name FROM bw_leaf WHERE parent_id = %s ORDER BY leaf_id",
            (node_id,),
        ).fetchall()
        children = tuple(
            self._build_subtree(int(row[0]), next_ancestors) for row in child_rows
        )
        return BandwidthTree(
            node_id=node_id,
            children=children,
            leaves=tuple(str(row[0]) for row in leaf_rows),
        )

    @staticmethod
    def _build_interface(row) -> BandwidthInterface:
        return BandwidthInterface(int(row[0]), str(row[1]), str(row[2] or ""))

    @staticmethod
    def _build_node(row) -> BandwidthNode:
        return BandwidthNode(
            node_id=int(row[0]),
            interface_id=int(row[1]),
            parent_id=int(row[2]) if row[2] is not None else None,
            rate_kbits=int(row[3]) if row[3] is not None else None,
            ceil_kbits=int(row[4]) if row[4] is not None else None,
        )


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
