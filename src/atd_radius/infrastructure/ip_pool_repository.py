"""PostgreSQL mapping for the native A1.24 IP pool tables."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Protocol

import psycopg


@dataclass(frozen=True, slots=True)
class IPPoolRecord:
    pool_id: int
    name: str
    comment: str | None


class IPPoolRepository(Protocol):
    def list(self) -> list[IPPoolRecord]: ...
    def get(self, pool_id: int) -> IPPoolRecord | None: ...
    def list_addresses(self, pool_id: int) -> tuple[str, ...]: ...
    def add_address(self, pool_id: int, address: str) -> None: ...
    def remove_address(self, pool_id: int, address: str) -> None: ...


class IPPoolSql:
    list_pools: ClassVar[str] = (
        "SELECT ippool_id, ippool_name, ippool_comment FROM ippool ORDER BY ippool_id"
    )
    pool: ClassVar[str] = (
        "SELECT ippool_id, ippool_name, ippool_comment FROM ippool WHERE ippool_id=%s"
    )
    list_addresses: ClassVar[str] = (
        "SELECT ip::text FROM ippool_ips WHERE ippool_id=%s ORDER BY ip"
    )
    add_address: ClassVar[str] = (
        "INSERT INTO ippool_ips(ippool_id, ip) VALUES (%s, %s::inet)"
    )
    remove_address: ClassVar[str] = (
        "DELETE FROM ippool_ips WHERE ippool_id=%s AND ip=%s::inet"
    )


class PostgresIPPoolRepository:
    """Native A1.24 ippool/ippool_ips persistence; no allocation table is invented."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def list(self) -> list[IPPoolRecord]:
        rows = self.conn.execute(IPPoolSql.list_pools).fetchall()
        return [self._record(row) for row in rows]

    def get(self, pool_id: int) -> IPPoolRecord | None:
        row = self.conn.execute(IPPoolSql.pool, (pool_id,)).fetchone()
        return self._record(row) if row else None

    def list_addresses(self, pool_id: int) -> tuple[str, ...]:
        rows = self.conn.execute(IPPoolSql.list_addresses, (pool_id,)).fetchall()
        return tuple(str(row[0]) for row in rows)

    def add_address(self, pool_id: int, address: str) -> None:
        self.conn.execute(IPPoolSql.add_address, (pool_id, address))

    def remove_address(self, pool_id: int, address: str) -> None:
        self.conn.execute(IPPoolSql.remove_address, (pool_id, address))

    @staticmethod
    def _record(row) -> IPPoolRecord:
        return IPPoolRecord(int(row[0]), str(row[1]), row[2])
