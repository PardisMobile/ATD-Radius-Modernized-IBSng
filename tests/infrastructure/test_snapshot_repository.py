from atd_radius.infrastructure.snapshot_repository import SnapshotSql
def test_snapshot_sql_targets_native_a124_tables():
    assert "internet_onlines_snapshot" in SnapshotSql.internet_insert
    assert "voip_onlines_snapshot" in SnapshotSql.voip_insert
    assert "ORDER BY snp_date DESC" in SnapshotSql.internet_search
