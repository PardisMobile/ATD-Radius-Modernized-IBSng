from atd_radius.infrastructure.connection_log_repository import ConnectionLogSql
from atd_radius.infrastructure.ip_pool_repository import IPPoolSql
def test_connection_log_uses_native_stored_function():
    assert "insert_connection_log" in ConnectionLogSql.insert_function
    assert "::text[]" in ConnectionLogSql.insert_function
def test_ip_pool_uses_native_ippool_tables():
    assert "ippool_ips" in IPPoolSql.list_addresses
    assert "inet" in IPPoolSql.add_address
    assert "ippool_comment" in IPPoolSql.pool
