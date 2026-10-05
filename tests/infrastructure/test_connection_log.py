from datetime import datetime,timezone
from atd_radius.infrastructure.connection_log import ConnectionLog

def test_connection_log_preserves_native_a124_fields():
    now=datetime.now(timezone.utc)
    row=ConnectionLog(9,12,"1.25",now,None,True,1,4,{"Acct-Session-Id":"abc"})
    assert row.service==1 and row.details["Acct-Session-Id"]=="abc"
