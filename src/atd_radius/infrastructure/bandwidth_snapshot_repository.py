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

    @staticmethod
    def bucket_time(snapshot_at: datetime, interval_seconds: int = 60) -> datetime:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        # A1.24 dbTimeFromEpoch uses time.localtime(), and the native column
        # is timestamp without time zone. Bucket by epoch, then store local time.
        epoch = int(snapshot_at.timestamp())
        bucket = epoch - (epoch % interval_seconds)
        return datetime.fromtimestamp(bucket)

    def record_usage(
        self,
        snapshot_at: datetime,
        user_id: int,
        input_delta: int,
        output_delta: int,
        interval_seconds: int = 60,
    ) -> None:
        if user_id < 0 or input_delta < 0 or output_delta < 0:
            raise ValueError("user IDs and bandwidth deltas must be non-negative")
        if input_delta == 0 and output_delta == 0:
            return
        self.conn.execute(
            self.UPSERT,
            (
                self.bucket_time(snapshot_at, interval_seconds),
                user_id,
                int(input_delta),
                int(output_delta),
            ),
        )

    def add_usage(
        self, snapshot_at: datetime, usage_by_user: dict[int, tuple[int, int]]
    ) -> None:
        # Match A1.24 dbTimeFromEpoch: convert aware instants to local server
        # time before writing into the timestamp-without-time-zone column.
        if snapshot_at.tzinfo is not None:
            snapshot_at = snapshot_at.astimezone().replace(tzinfo=None)
        for user_id, (input_delta, output_delta) in sorted(usage_by_user.items()):
            if user_id < 0 or input_delta < 0 or output_delta < 0:
                raise ValueError("user IDs and bandwidth deltas must be non-negative")
            if input_delta == 0 and output_delta == 0:
                continue
            self.conn.execute(
                self.UPSERT,
                (snapshot_at, user_id, int(input_delta), int(output_delta)),
            )
