from atd_radius.infrastructure.user_assigned_ip_repository import PostgresUserAssignedIPRepository

class Result:
    def __init__(self,row=None,rows=()): self.row=row; self.rows=list(rows)
    def fetchone(self): return self.row
    def fetchall(self): return self.rows
class Connection:
    def __init__(self,results=()): self.results=list(results); self.calls=[]
    def execute(self,sql,params=()):
        self.calls.append((sql,params)); return self.results.pop(0) if self.results else Result()

def test_reservation_locks_and_allocates_first_available_address():
    conn=Connection([Result(),Result(),Result(("192.0.2.11",))]); repo=PostgresUserAssignedIPRepository(conn)
    assert repo.reserve(4,"192.0.2.10, 192.0.2.11","a"*64)=="192.0.2.11"
    assert "pg_advisory_xact_lock" in conn.calls[0][0] and conn.calls[0][1]==("assign-ip:4",)
    assert "ON CONFLICT(ip_address) DO NOTHING" in conn.calls[2][0]

def test_retry_is_idempotent_and_request_key_is_user_scoped():
    repo=PostgresUserAssignedIPRepository(Connection([Result((4,"192.0.2.11"))]))
    assert repo.reserve(4,"192.0.2.10,192.0.2.11","retry")=="192.0.2.11"
    repo=PostgresUserAssignedIPRepository(Connection([Result((9,"192.0.2.11"))]))
    try: repo.reserve(4,"192.0.2.11","retry")
    except ValueError as exc: assert "another user" in str(exc)
    else: raise AssertionError("request-key collision must fail closed")

def test_specific_reservation_promotes_to_exact_session():
    conn=Connection([Result(),Result(("192.0.2.12",)),Result((1,))]); repo=PostgresUserAssignedIPRepository(conn)
    assert repo.reserve_specific(4,"192.0.2.11,192.0.2.12","req","192.0.2.12")=="192.0.2.12"
    assert repo.bind_session(4,3,"session-1","192.0.2.12")
    assert conn.calls[2][1]==(3,"session-1",4,"192.0.2.12")

def test_release_is_exact_and_stop_idempotent():
    conn=Connection([Result(),Result(("192.0.2.12",))]); repo=PostgresUserAssignedIPRepository(conn)
    assert repo.release_session(4,3,"session-1")=="192.0.2.12"
    assert conn.calls[-1][1]==(4,3,"session-1")

def test_empty_pool_is_no_address():
    conn=Connection(); repo=PostgresUserAssignedIPRepository(conn)
    assert repo.reserve(4,None,"empty") is None and conn.calls==[]


def test_configured_addresses_are_canonicalized_and_deduplicated():
    assert PostgresUserAssignedIPRepository._configured(["192.0.2.1", "192.0.2.1", "2001:0db8::1", "2001:db8::1"]) == ("192.0.2.1", "2001:db8::1")

def test_invalid_configured_address_fails_closed():
    try:
        PostgresUserAssignedIPRepository._configured(["not-an-ip"])
    except ValueError:
        pass
    else:
        raise AssertionError("invalid configured IP must not reach allocation")

def test_pending_expiration_reports_count_and_only_targets_pending_leases():
    conn = Connection([Result((3,))]); repo = PostgresUserAssignedIPRepository(conn)
    assert repo.expire_pending(180) == 3
    sql, params = conn.calls[-1]
    assert "status='pending'" in sql and "INTERVAL '1 second'" in sql and params == (180,)

def test_pending_expiration_rejects_nonpositive_age():
    repo = PostgresUserAssignedIPRepository(Connection())
    try:
        repo.expire_pending(0)
    except ValueError:
        pass
    else:
        raise AssertionError("expiration age must be positive")
