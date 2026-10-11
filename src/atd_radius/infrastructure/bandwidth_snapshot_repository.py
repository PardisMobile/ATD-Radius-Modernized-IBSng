"""PostgreSQL persistence for the native A1.24 internet_bw_snapshot table."""
from __future__ import annotations

from datetime import datetime


class PostgresBandwidthSnapshotRepository:
    """Write aggregated per-user bandwidth deltas into native snapshot storage."""

    UPSERT = """INSERT INTO internet_bw_snapshot (snp_date, user_id, in_rate, out_rate)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, snp_date) DO UPDATE
                SET in_rate = internet_bw_snapshot.in_rate + EXCLUDED.in_rate,
                    out_rate = internet_bw_snapshot.out_rate + EXCLUDED.out_rate"""

    def __init__(self, conn) -> None:
        self.conn = conn

    def add_usage(
        self, snapshot_at: datetime, usage_by_user: dict[int, tuple[int, int]]
    ) -> None:
        for user_id, (input_delta, output_delta) in sorted(usage_by_user.items()):
            if user_id < 0 or input_delta < 0 or output_delta < 0:
                raise ValueError("user IDs and bandwidth deltas must be non-negative")
            if input_delta == 0 and output_delta == 0:
                continue
            self.conn.execute(
                self.UPSERT,
                (snapshot_at, user_id, int(input_delta), int(output_delta)),
            )
