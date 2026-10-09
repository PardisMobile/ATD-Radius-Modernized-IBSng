from __future__ import annotations

from datetime import datetime, timezone

import pytest

from atd_radius.infrastructure.operational_audit import OperationalAuditRepository


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.query = query
        self.params = params
        return FakeCursor((17, datetime(2026, 10, 9, tzinfo=timezone.utc)))


def test_append_writes_authenticated_actor_and_structured_details():
    conn = FakeConnection()
    event = OperationalAuditRepository(conn).append(
        actor_admin_id=7,
        actor_username="operator",
        action="ras.disconnect.request",
        outcome="success",
        target_type="session",
        target_id="session-42",
        remote_addr="192.0.2.10",
        request_id="req-abc",
        details={"provider": "cisco", "dry_run": True},
    )

    assert event.event_id == 17
    assert event.occurred_at == "2026-10-09T00:00:00+00:00"
    assert "INSERT INTO operational_audit_events" in conn.query
    assert conn.params[:8] == (
        7, "operator", "ras.disconnect.request", "success",
        "session", "session-42", "192.0.2.10", "req-abc",
    )
    assert conn.params[8] == '{"dry_run":true,"provider":"cisco"}'


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"actor_admin_id": -1, "actor_username": "operator", "action": "x", "outcome": "success"}, "actor_admin_id"),
        ({"actor_admin_id": 1, "actor_username": " ", "action": "x", "outcome": "success"}, "actor_username"),
        ({"actor_admin_id": 1, "actor_username": "operator", "action": "x", "outcome": "unknown"}, "outcome"),
        ({"actor_admin_id": 1, "actor_username": "operator", "action": "x", "outcome": "success", "details": ["not", "object"]}, "details"),
    ],
)
def test_append_rejects_invalid_audit_records_before_database_write(kwargs, message):
    conn = FakeConnection()
    with pytest.raises(ValueError, match=message):
        OperationalAuditRepository(conn).append(**kwargs)
    assert conn.query is None
