from atd_radius.infrastructure.ip_pool_repository import IPPoolSql


def test_ip_pool_sql_uses_native_a124_tables_and_psycopg_placeholders():
    assert "FROM ippool " in IPPoolSql.list_pools
    assert "FROM ippool WHERE ippool_id=%s" in IPPoolSql.pool
    assert "FROM ippool_ips" in IPPoolSql.list_addresses
    assert "%s" in IPPoolSql.add_address
    assert "%s" in IPPoolSql.remove_address
    assert "$1" not in IPPoolSql.list_pools + IPPoolSql.pool + IPPoolSql.list_addresses
    assert "$1" not in IPPoolSql.add_address + IPPoolSql.remove_address
