"""A1.24 internet bandwidth snapshot aggregation and persistence boundary."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class BandwidthSnapshotWriter(Protocol):
    def add_usage(self, snapshot_at: datetime, usage_by_user: dict[int, tuple[int, int]]) -> None: ...


class InternetBandwidthSnapshotCollector:
    """Aggregate per-user byte deltas for one source-style snapshot cycle.

    A1.24's BWSnapShotOnlinesLoopClient aggregates input/output rates across
    all active instances per user, then writes one row per user at loopEnd.
    The caller is responsible for feeding deltas only for normal users whose
    effective attributes include save_bw_usage.
    """

    def __init__(self, writer: BandwidthSnapshotWriter) -> None:
        self.writer = writer
        self._usage: dict[int, list[int]] = {}

    def record(self, user_id: int, input_delta: int, output_delta: int) -> None:
        if user_id < 0:
            raise ValueError("user_id cannot be negative")
        if input_delta < 0 or output_delta < 0:
            raise ValueError("bandwidth deltas cannot be negative")
        if input_delta == 0 and output_delta == 0:
            return
        usage = self._usage.setdefault(user_id, [0, 0])
        usage[0] += input_delta
        usage[1] += output_delta

    def pending(self) -> dict[int, tuple[int, int]]:
        return {user_id: (values[0], values[1]) for user_id, values in sorted(self._usage.items())}

    def flush(self, snapshot_at: datetime | None = None) -> int:
        """Persist this cycle once; return number of users written.

        State is cleared only after the writer succeeds, so a failed database
        write can be retried without silently losing collected usage.
        """
        batch = self.pending()
        if not batch:
            return 0
        timestamp = snapshot_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        self.writer.add_usage(timestamp, batch)
        self._usage.clear()
        return len(batch)
