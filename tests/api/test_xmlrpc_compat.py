import xmlrpc.client
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

import atd_radius.api.xmlrpc_compat as api
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.ias_events_repository import IASEvent


class FakeConnection:
    def __init__(self):
        self.committed = False
    def commit(self):
        self.committed = True


def install_admin(monkeypatch, *, god=True):
    conn = FakeConnection()
    @contextmanager
    def fake_connection():
        yield conn
    class Authenticator:
        def __init__(self, _repo):
            pass
        def authenticate(self, username, password, remote_addr):
            assert username == "admin"
            assert password == "secret"
            assert remote_addr == "127.0.0.1"
            return SimpleNamespace(admin_id=7, username="admin")
    class AdminRepo:
        def __init__(self, _conn):
            pass
        def permissions(self, _admin_id):
            return AdminPermissionSet({"GOD": ""} if god else {})
    monkeypatch.setattr(api, "connection", fake_connection)
    monkeypatch.setattr(api, "AdminAuthenticator", Authenticator)
    monkeypatch.setattr(api, "AdminRepository", AdminRepo)
    return conn


def test_xmlrpc_get_events_uses_registered_native_method_and_returns_db_fields(monkeypatch):
    install_admin(monkeypatch)
    event = IASEvent(3, 1, datetime(2026, 10, 12, 10), "admin", Decimal("10.5"), "1", "credit")
    class Events:
        def __init__(self, _conn):
            pass
        def list_events(self, from_event_id, offset, to):
            assert (from_event_id, offset, to) == (1, 0, 10)
            return [event]
    monkeypatch.setattr(api, "PostgresIASEventRepository", Events)
    result = api._execute_ias_method(
        "ias.getEvents",
        ({"auth_type": "ADMIN", "auth_name": "admin", "auth_pass": "secret",
          "from_event_id": 1, "from": 0, "to": 10},),
        "127.0.0.1",
    )
    assert result[0]["event_id"] == 3
    assert result[0]["event_type"] == 1
    assert result[0]["amount"] == 10.5
    assert result[0]["event_date"] == event.event_date


def test_xmlrpc_ias_is_god_only_due_to_unregistered_source_permission(monkeypatch):
    install_admin(monkeypatch, god=False)
    with pytest.raises(PermissionError, match="Access denied"):
        api._execute_ias_method(
            "ias.getEvents",
            ({"auth_type": "ADMIN", "auth_name": "admin", "auth_pass": "secret",
              "from_event_id": 0, "from": 0, "to": 1},),
            "127.0.0.1",
        )


def test_xmlrpc_delete_events_returns_empty_string_and_commits(monkeypatch):
    conn = install_admin(monkeypatch)
    class Events:
        def __init__(self, _conn):
            pass
        def delete_events(self, event_ids):
            assert event_ids == [4, 5]
            return 2
    class Audit:
        def __init__(self, _conn):
            pass
        def append(self, **kwargs):
            assert kwargs["action"] == "ias.events.delete"
    monkeypatch.setattr(api, "PostgresIASEventRepository", Events)
    monkeypatch.setattr(api, "OperationalAuditRepository", Audit)
    result = api._execute_ias_method(
        "ias.deleteEvents",
        ({"auth_type": "ADMIN", "auth_name": "admin", "auth_pass": "secret",
          "event_ids": [4, 5]},),
        "127.0.0.1",
    )
    assert result == ""
    assert conn.committed is True


def test_xmlrpc_endpoint_parses_request_and_serializes_faults(monkeypatch):
    async def body():
        return xmlrpc.client.dumps(
            ({"auth_type": "ADMIN", "auth_name": "admin", "auth_pass": "secret"},),
            methodname="ias.getIASUserInfo",
        ).encode()
    request = SimpleNamespace(body=body, client=SimpleNamespace(host="127.0.0.1"))
    monkeypatch.setattr(api, "_execute_ias_method", lambda method, params, remote: [{"user_id": "1"}])
    response = __import__("asyncio").run(api.xmlrpc_compatibility_endpoint(request))
    parsed, method = xmlrpc.client.loads(response.body)
    assert method is None
    assert parsed[0] == [{"user_id": "1"}]
    assert response.media_type == "text/xml"


def test_xmlrpc_compatibility_rejects_unregistered_handlers(monkeypatch):
    install_admin(monkeypatch)
    with pytest.raises(ValueError, match="no registered method"):
        api._execute_ias_method("user.getInfo", ({},), "127.0.0.1")



def test_xmlrpc_endpoint_enforces_body_limit_while_streaming(monkeypatch):
    monkeypatch.setattr(api, "_MAX_BODY_BYTES", 8)
    consumed = []

    async def stream():
        consumed.append("first")
        yield b"123456"
        consumed.append("second")
        yield b"789"

    request = SimpleNamespace(
        stream=stream,
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    response = __import__("asyncio").run(api.xmlrpc_compatibility_endpoint(request))
    with pytest.raises(xmlrpc.client.Fault, match="too large"):
        xmlrpc.client.loads(response.body)
    assert consumed == ["first", "second"]


def test_xmlrpc_endpoint_rejects_declared_oversize_without_reading_body(monkeypatch):
    monkeypatch.setattr(api, "_MAX_BODY_BYTES", 8)
    async def stream():
        raise AssertionError("oversized body should be rejected before reading")
        yield b""
    request = SimpleNamespace(
        stream=stream,
        headers={"content-length": "9"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    response = __import__("asyncio").run(api.xmlrpc_compatibility_endpoint(request))
    with pytest.raises(xmlrpc.client.Fault, match="too large"):
        xmlrpc.client.loads(response.body)
