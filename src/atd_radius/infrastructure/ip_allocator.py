from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg


@dataclass(frozen=True)
class AllocatedAddress:
    pool_id: UUID
    address: str
    user_id: UUID | None


class PostgresIPAllocator:
    """Concurrency-safe allocator using row locks and an explicit lease record."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def allocate(self, pool_id: UUID, user_id: UUID | None = None) -> AllocatedAddress | None:
        with self.conn.transaction():
            row = self.conn.execute(
                """
                SELECT address
                FROM ip_pool_addresses
                WHERE pool_id = %s AND state = 'available'
                ORDER BY address
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (pool_id,),
            ).fetchone()
            if row is None:
                return None

            address = row[0]
            self.conn.execute(
                """
                UPDATE ip_pool_addresses
                SET state = 'allocated', user_id = %s, updated_at = now()
                WHERE pool_id = %s AND address = %s
                """,
                (user_id, pool_id, address),
            )
            self.conn.execute(
                """
                INSERT INTO ip_allocations (pool_id, address, user_id)
                VALUES (%s, %s, %s)
                """,
                (pool_id, address, user_id),
            )
            return AllocatedAddress(pool_id=pool_id, address=str(address), user_id=user_id)

    def release(self, pool_id: UUID, address: str) -> None:
        with self.conn.transaction():
            self.conn.execute(
                """
                UPDATE ip_pool_addresses
                SET state = 'available', user_id = NULL, updated_at = now()
                WHERE pool_id = %s AND address = %s AND state = 'allocated'
                """,
                (pool_id, address),
            )
            self.conn.execute(
                """
                UPDATE ip_allocations
                SET released_at = now()
                WHERE pool_id = %s AND address = %s AND released_at IS NULL
                """,
                (pool_id, address),
            )
