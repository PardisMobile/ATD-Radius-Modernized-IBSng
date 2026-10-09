from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import atd_radius.api.admin_dependencies as dependencies


class Cursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, locked, permissions):
        self.results = [
            Cursor(row=(10, 7, "operator", datetime(2030, 1, 1, tzinfo=timezone.utc), "192.0.2.10")),
            Cursor(row=(1,) if locked else None),
            Cursor(rows=permissions),
        ]

    def execute(self, query, params):
        return self.results.pop(0)


def request():
    return Request({"type": "http", "headers": [], "client": ("192.0.2.20", 1234), "method": "GET", "path": "/api/v1/ras"})


def call_permission(monkeypatch, permissions, required, locked=False):
    conn = FakeConnection(locked, permissions)

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(dependencies, "connection", fake_connection)
    dependency = dependencies.require_admin_permission(required)
    return dependency(request(), "session-token")


def test_source_ras_permission_dependencies_are_enforced(monkeypatch):
    principal = call_permission(monkeypatch, [("LIST RAS", "")], "LIST RAS")
    assert principal.admin_id == 7
    assert principal.username == "operator"
    assert principal.remote_addr == "192.0.2.20"

    with pytest.raises(HTTPException) as denied:
        call_permission(monkeypatch, [("GET RAS INFORMATION", "")], "GET RAS INFORMATION")
    assert denied.value.status_code == 403

    with pytest.raises(HTTPException) as denied:
        call_permission(monkeypatch, [("LIST RAS", ""), ("CHANGE RAS", "")], "CHANGE RAS")
    assert denied.value.status_code == 403

    principal = call_permission(
        monkeypatch,
        [("LIST RAS", ""), ("GET RAS INFORMATION", ""), ("CHANGE RAS", "")],
        "CHANGE RAS",
    )
    assert principal.admin_id == 7


def test_god_bypass_does_not_bypass_native_admin_lock(monkeypatch):
    principal = call_permission(monkeypatch, [("GOD", "")], "CHANGE RAS")
    assert principal.admin_id == 7

    with pytest.raises(HTTPException) as denied:
        call_permission(monkeypatch, [("GOD", "")], "CHANGE RAS", locked=True)
    assert denied.value.status_code == 403
