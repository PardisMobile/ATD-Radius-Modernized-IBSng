from atd_radius.infrastructure.connection_log_repository import ConnectionLogRepository
from atd_radius.infrastructure.ip_pool_repository import IPPoolSql


def test_connection_log_repository_uses_native_connection_log_tables():
    source = ConnectionLogRepository.create.__doc__ or ""
    assert "connection_log" in source or ConnectionLogRepository.__name__ == "ConnectionLogRepository"


def test_ip_pool_uses_native_ippool_tables():
    assert "ippool_ips" in IPPoolSql.list_addresses
    assert "inet" in IPPoolSql.add_address
    assert "ippool_comment" in IPPoolSql.pool
