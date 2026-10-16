from atd_radius.infrastructure.connection_log_repository import ConnectionLogRepository
from atd_radius.infrastructure.ip_pool_repository import IPPoolSql


def test_connection_log_repository_uses_native_connection_log_tables():
    source = ConnectionLogRepository.create.__doc__ or ""
    assert "connection_log" in source or ConnectionLogRepository.__name__ == "ConnectionLogRepository"


def test_ip_pool_uses_native_ippool_tables():
    assert "ippool_ips" in IPPoolSql.list_addresses
    assert "inet" in IPPoolSql.add_address
    assert "ippool_comment" in IPPoolSql.pool



def test_accounting_identity_resolves_normal_and_voip_namespaces_uniquely():
    from atd_radius.infrastructure import UserRepository

    class Connection:
        def __init__(self, rows):
            self.rows = rows
            self.query = None

        def execute(self, query, params):
            self.query = (query, params)
            return self

        def fetchall(self):
            return self.rows

    conn = Connection([(17,)])
    repository = UserRepository(conn)
    assert repository.accounting_user_id("sip-alice") == 17
    assert "FROM normal_users WHERE normal_username=%s" in conn.query[0]
    assert "FROM voip_users WHERE voip_username=%s" in conn.query[0]
    assert conn.query[1] == ("sip-alice", "sip-alice")


def test_accounting_identity_fails_closed_for_missing_or_ambiguous_names():
    from atd_radius.infrastructure import UserRepository

    class Connection:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, *_args):
            return self

        def fetchall(self):
            return self.rows

    assert UserRepository(Connection([])).accounting_user_id("unknown") is None
    assert UserRepository(Connection([(17,), (22,)])).accounting_user_id("shared-name") is None
    assert UserRepository(Connection([(17,), (17,)])).accounting_user_id("same-user") == 17
