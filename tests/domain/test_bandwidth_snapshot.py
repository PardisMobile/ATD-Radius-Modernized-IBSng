from datetime import datetime, timezone

import pytest

from atd_radius.domain.bandwidth_snapshot import InternetBandwidthSnapshotCollector
from atd_radius.infrastructure.bandwidth_snapshot_repository import (
    PostgresBandwidthSnapshotRepository,
)


class Writer:
    def __init__(self, fail=False):
        self.batches = []
        self.fail = fail

    def add_usage(self, snapshot_at, usage_by_user):
        if self.fail:
            raise RuntimeError("database unavailable")
        self.batches.append((snapshot_at, usage_by_user))


class FakeConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_collector_aggregates_multiple_instance_deltas_per_user_and_flushes_once():
    writer = Writer()
    collector = InternetBandwidthSnapshotCollector(writer)
    collector.record(8, 100, 200)
    collector.record(8, 50, 70)
    collector.record(3, 0, 25)
    collector.record(3, 0, 0)

    assert collector.pending() == {3: (0, 25), 8: (150, 270)}
    assert collector.flush(datetime(2026, 10, 12, 12, tzinfo=timezone.utc)) == 2
    assert writer.batches == [
        (datetime(2026, 10, 12, 12), {3: (0, 25), 8: (150, 270)})
    ]
    assert collector.pending() == {}
    assert collector.flush() == 0


def test_failed_flush_retains_usage_for_retry():
    writer = Writer(fail=True)
    collector = InternetBandwidthSnapshotCollector(writer)
    collector.record(8, 100, 200)

    with pytest.raises(RuntimeError):
        collector.flush(datetime(2026, 10, 12, 12))
    assert collector.pending() == {8: (100, 200)}

    writer.fail = False
    assert collector.flush(datetime(2026, 10, 12, 12)) == 1
    assert collector.pending() == {}


def test_collector_rejects_negative_identity_or_counter_delta():
    collector = InternetBandwidthSnapshotCollector(Writer())
    with pytest.raises(ValueError):
        collector.record(-1, 1, 1)
    with pytest.raises(ValueError):
        collector.record(1, -1, 0)
    with pytest.raises(ValueError):
        collector.record(1, 0, -1)


def test_postgres_repository_uses_native_table_and_accumulates_duplicate_timestamp():
    conn = FakeConnection()
    repository = PostgresBandwidthSnapshotRepository(conn)
    timestamp = datetime(2026, 10, 12, 12)
    repository.add_usage(timestamp, {8: (100, 200), 3: (50, 60), 4: (0, 0)})

    assert len(conn.calls) == 2
    sql, params = conn.calls[0]
    assert "INSERT INTO internet_bw_snapshot" in sql
    assert "ON CONFLICT (user_id, snp_date)" in sql
    assert "internet_bw_snapshot.in_rate + EXCLUDED.in_rate" in sql
    assert params == (timestamp, 3, 50, 60)
