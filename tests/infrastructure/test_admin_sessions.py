from datetime import datetime, timezone

from atd_radius.infrastructure.admin_sessions import AdminSessionRepository


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return Cursor(self.rows.pop(0))


def test_session_creation_stores_only_sha256_digest():
    conn = FakeConnection([(12,)])
    repo = AdminSessionRepository(conn)
    token = "random-one-time-secret"
    session_id = repo.create(
        token=token,
        admin_id=7,
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        remote_addr="192.0.2.10",
    )
    assert session_id == 12
    stored_digest = conn.calls[0][1][1]
    assert stored_digest == repo.digest(token)
    assert stored_digest != token
    assert len(stored_digest) == 64


def test_active_session_requires_nonrevoked_unexpired_database_row():
    expiry = datetime(2030, 1, 1, tzinfo=timezone.utc)
    conn = FakeConnection([(12, 7, "operator", expiry, "192.0.2.10")])
    session = AdminSessionRepository(conn).get_active("secret")
    assert session.session_id == 12
    assert session.admin_id == 7
    assert session.username == "operator"
    assert session.remote_addr == "192.0.2.10"
    query = conn.calls[0][0]
    assert "revoked_at IS NULL" in query
    assert "expires_at > CURRENT_TIMESTAMP" in query


def test_revocation_is_idempotent_and_reports_whether_a_row_changed():
    repo = AdminSessionRepository(FakeConnection([(12,), None]))
    assert repo.revoke("secret")
    assert not repo.revoke("secret")


def test_empty_session_token_is_rejected():
    try:
        AdminSessionRepository.digest("")
    except ValueError as exc:
        assert str(exc) == "session token is required"
    else:
        raise AssertionError("empty token must not be hashed")
