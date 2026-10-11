import pytest

from atd_radius.infrastructure.snapshot_repository import SnapshotSql
def test_snapshot_sql_targets_native_a124_tables():
    assert "internet_onlines_snapshot" in SnapshotSql.internet_insert
    assert "voip_onlines_snapshot" in SnapshotSql.voip_insert
    assert "ORDER BY snp_date DESC" in SnapshotSql.internet_search


from datetime import datetime, timezone

from atd_radius.infrastructure.bandwidth_snapshot_repository import (
    PostgresBandwidthSnapshotRepository,
)


class FakeConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_bandwidth_snapshot_buckets_to_native_default_one_minute_interval():
    conn = FakeConnection()
    repo = PostgresBandwidthSnapshotRepository(conn)
    repo.record_usage(
        datetime(2026, 10, 12, 12, 1, 59, tzinfo=timezone.utc),
        7,
        100,
        200,
    )
    sql, params = conn.calls[0]
    assert "INSERT INTO internet_bw_snapshot" in sql
    assert params == (datetime(2026, 10, 12, 12, 1), 7, 100, 200)


def test_bandwidth_snapshot_normalizes_timezone_and_accumulates_by_native_key():
    conn = FakeConnection()
    repo = PostgresBandwidthSnapshotRepository(conn)
    repo.record_usage(
        datetime(2026, 10, 12, 14, 1, 20, tzinfo=timezone.utc),
        7,
        50,
        60,
    )
    sql, params = conn.calls[0]
    assert "ON CONFLICT (user_id, snp_date)" in sql
    assert "out_rate = internet_bw_snapshot.out_rate + EXCLUDED.out_rate" in sql
    assert params == (datetime(2026, 10, 12, 14, 1), 7, 50, 60)


def test_bandwidth_snapshot_rejects_invalid_interval_and_negative_deltas():
    conn = FakeConnection()
    repo = PostgresBandwidthSnapshotRepository(conn)
    with pytest.raises(ValueError):
        repo.record_usage(datetime(2026, 10, 12), 7, 1, 1, interval_seconds=0)
    with pytest.raises(ValueError):
        repo.record_usage(datetime(2026, 10, 12), 7, -1, 1)
