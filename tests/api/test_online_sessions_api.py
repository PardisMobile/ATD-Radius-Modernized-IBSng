from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from atd_radius.api import online_sessions as api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry


class Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, *, session_rows=(), reservation_rows=(), owner_row=(8,)):
        self.session_rows = list(session_rows)
        self.reservation_rows = list(reservation_rows)
        self.owner_row = owner_row
        self.committed = False

    def execute(self, sql, _params=()):
        if "FROM atd_radius_live_sessions" in sql:
            return Result(self.session_rows)
        if "FROM atd_radius_login_reservations" in sql:
            return Result(self.reservation_rows)
        if "SELECT owner_id FROM users" in sql:
            return Result([self.owner_row] if self.owner_row is not None else [])
        return Result([])

    def commit(self):
        self.committed = True


class ConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *_args):
        return False


def _admin():
    return AdminPrincipal(8, "admin", "192.0.2.10", Mock())


def test_list_online_sessions_returns_safe_session_fields_and_login_reservations(monkeypatch):
    state = {
        "attributes": {
            "User-Name": "alice",
            "Framed-IP-Address": "198.51.100.20",
            "NAS-Port": "17",
        },
        "started_at": "2026-10-21T12:00:00+00:00",
        "charge_kind": "internet",
        "input_octets": 100,
        "output_octets": 200,
        "termination_requested_reason": None,
    }
    created_at = datetime(2026, 10, 21, 12, 1, tzinfo=timezone.utc)
    conn = Connection(
        session_rows=[(7, 3, "sid-7", state, 8, "alice")],
        reservation_rows=[(7, 3, "alice", created_at, True, 8, "alice")],
    )
    monkeypatch.setattr(api, "connection", lambda: ConnectionContext(conn))
    monkeypatch.setattr(api, "can_see_online_users", lambda _admin, _owner_id: True)

    result = api.list_online_sessions(_admin())

    assert len(result.sessions) == 1
    session = result.sessions[0]
    assert session.user_id == 7
    assert session.username == "alice"
    assert session.remote_ip == "198.51.100.20"
    assert session.nas_port == "17"
    assert session.input_octets == 100
    assert session.output_octets == 200
    assert session.termination_requested is False
    assert len(result.login_in_progress) == 1
    assert result.login_in_progress[0].ras_multi_login_allowed is True


def test_kill_online_session_checks_permission_and_audits_provider_request(monkeypatch):
    conn = Connection()
    registry = SessionRegistry()
    registry.start(SessionKey(7, 3, "sid-7"), {"User-Name": "alice"})
    handler = SimpleNamespace(
        state=SimpleNamespace(sessions=registry),
        _refresh_durable_user_sessions=Mock(),
        _terminate_voip_session=Mock(),
    )
    request = SimpleNamespace(app=SimpleNamespace(
        state=SimpleNamespace(radius_packet_handler=handler)
    ))
    audit = Mock()
    monkeypatch.setattr(api, "connection", lambda: ConnectionContext(conn))
    monkeypatch.setattr(api, "can_kill_user", lambda _admin, owner_id: owner_id == 8)
    monkeypatch.setattr(api, "OperationalAuditRepository", lambda _conn: audit)

    result = api.kill_online_session(
        api.KillOnlineSessionPayload(user_id=7, ras_id=3, unique_id="sid-7"),
        request,
        _admin(),
    )

    assert result.termination_requested is True
    handler._refresh_durable_user_sessions.assert_called_once()
    handler._terminate_voip_session.assert_called_once_with(
        SessionKey(7, 3, "sid-7"), "killed_by_admin:admin"
    )
    audit.append.assert_called_once()
    assert audit.append.call_args.kwargs["outcome"] == "success"



def test_clear_online_session_uses_local_no_debit_path_and_audits(monkeypatch):
    conn = Connection()
    clear_method = Mock()
    handler = SimpleNamespace(clear_user_session=clear_method)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(radius_packet_handler=handler)))
    audit = Mock()
    monkeypatch.setattr(api, "connection", lambda: ConnectionContext(conn))
    monkeypatch.setattr(api, "can_clear_user", lambda _admin, owner_id: owner_id == 8)
    monkeypatch.setattr(api, "OperationalAuditRepository", lambda _conn: audit)

    result = api.clear_online_session(
        api.KillOnlineSessionPayload(user_id=7, ras_id=3, unique_id="sid-7"),
        request,
        _admin(),
    )

    assert result.cleared_locally is True
    assert result.credit_deducted is False
    assert result.ras_disconnect_sent is False
    clear_method.assert_called_once_with(SessionKey(7, 3, "sid-7"))
    audit.append.assert_called_once()
    assert audit.append.call_args.kwargs["action"] == "user.session.clear"
    assert audit.append.call_args.kwargs["details"]["credit_deducted"] is False
