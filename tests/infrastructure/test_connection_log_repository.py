from datetime import datetime
from unittest.mock import Mock

from atd_radius.infrastructure.connection_log import ConnectionLog
from atd_radius.infrastructure.connection_log_repository import ConnectionLogRepository


def test_create_allocates_native_connection_log_id_and_persists_details():
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = (42,)
    repository = ConnectionLogRepository(conn)
    record = ConnectionLog(
        connection_log_id=0,
        user_id=7,
        credit_used="12.50",
        login_time=datetime(2026, 10, 6, 10, 0),
        logout_time=None,
        successful=True,
        service=1,
        ras_id=3,
        details={"Acct-Session-Id": "abc"},
    )

    assert repository.create(record) == 42

    assert conn.execute.call_count == 3
    assert "nextval('connection_log_id')" in conn.execute.call_args_list[0].args[0]
    assert "INSERT INTO connection_log" in conn.execute.call_args_list[1].args[0]
    assert "INSERT INTO connection_log_details" in conn.execute.call_args_list[2].args[0]


def test_close_updates_native_connection_log():
    conn = Mock()
    repository = ConnectionLogRepository(conn)

    repository.close(42, datetime(2026, 10, 6, 11, 0), "20.00", True)

    sql, params = conn.execute.call_args.args
    assert "UPDATE connection_log" in sql
    assert params == (datetime(2026, 10, 6, 11, 0), "20.00", True, 42)
