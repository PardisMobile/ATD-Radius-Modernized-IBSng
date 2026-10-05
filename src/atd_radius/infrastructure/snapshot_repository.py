"""PostgreSQL snapshot SQL for A1.24 online counters."""
from typing import ClassVar

class SnapshotSql:
    internet_insert: ClassVar[str] = "INSERT INTO internet_onlines_snapshot(snp_date,ras_id,value) VALUES (%s,%s,%s)"
    voip_insert: ClassVar[str] = "INSERT INTO voip_onlines_snapshot(snp_date,ras_id,value) VALUES (%s,%s,%s)"
    internet_search: ClassVar[str] = "SELECT snp_date,ras_id,value FROM internet_onlines_snapshot WHERE ras_id=%s ORDER BY snp_date DESC"
    voip_search: ClassVar[str] = "SELECT snp_date,ras_id,value FROM voip_onlines_snapshot WHERE ras_id=%s ORDER BY snp_date DESC"
