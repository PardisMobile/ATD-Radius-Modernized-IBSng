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
    principal = dependencies.require_admin_session(request(), "session-token")
    dependency = dependencies.require_admin_permission(required)
    return dependency(principal)


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



def test_group_visibility_matches_owner_and_explicit_access_rules(monkeypatch):
    from atd_radius.api.admin_dependencies import AdminPrincipal, can_use_group
    from atd_radius.domain.admin_permissions import AdminPermissionSet

    owned = AdminPrincipal(7, "operator", None, AdminPermissionSet({}))
    assert can_use_group(owned, "team-a", 7)
    assert not can_use_group(owned, "team-b", 8)

    group_access = AdminPrincipal(
        7, "operator", None, AdminPermissionSet({"GROUP ACCESS": "team-b,team-c"})
    )
    assert can_use_group(group_access, "team-b", 8)
    assert not can_use_group(group_access, "team-d", 8)

    all_groups = AdminPrincipal(
        7, "operator", None, AdminPermissionSet({"ACCESS ALL GROUPS": ""})
    )
    assert can_use_group(all_groups, "team-z", 99)

    god = AdminPrincipal(7, "operator", None, AdminPermissionSet({"GOD": ""}))
    assert can_use_group(god, "team-z", 99)



def test_user_permission_values_enforce_owner_scope_and_dependencies():
    from atd_radius.api.admin_dependencies import (
        AdminPrincipal,
        can_access_user,
        can_change_user,
        can_delete_user,
    )
    from atd_radius.domain.admin_permissions import AdminPermissionSet

    restricted = AdminPrincipal(
        7, "operator", None,
        AdminPermissionSet({
            "GET USER INFORMATION": "Restricted",
            "CHANGE USER ATTRIBUTES": "Restricted",
            "DELETE USER": "Restricted",
        }),
    )
    assert can_access_user(restricted, 7)
    assert not can_access_user(restricted, 8)
    assert can_change_user(restricted, 7)
    assert not can_change_user(restricted, 8)
    assert can_delete_user(restricted, 7)
    assert not can_delete_user(restricted, 8)

    without_dependency = AdminPrincipal(
        7, "operator", None, AdminPermissionSet({"CHANGE USER ATTRIBUTES": "All"})
    )
    assert not can_change_user(without_dependency, 7)

    all_users = AdminPrincipal(
        7, "operator", None,
        AdminPermissionSet({
            "GET USER INFORMATION": "All",
            "CHANGE USER ATTRIBUTES": "All",
            "DELETE USER": "All",
        }),
    )
    assert can_access_user(all_users, 999)
    assert can_change_user(all_users, 999)
    assert can_delete_user(all_users, 999)

    god = AdminPrincipal(7, "operator", None, AdminPermissionSet({"GOD": ""}))
    assert can_access_user(god, 999)
    assert can_change_user(god, 999)
    assert can_delete_user(god, 999)


def test_connection_logs_and_credit_changes_require_their_own_source_permissions():
    from atd_radius.api.admin_dependencies import (
        AdminPrincipal,
        can_view_connection_logs,
        can_view_credit_changes,
    )
    from atd_radius.domain.admin_permissions import AdminPermissionSet

    no_report_permissions = AdminPrincipal(
        7, "operator", None, AdminPermissionSet({"GET USER INFORMATION": "All"})
    )
    assert not can_view_connection_logs(no_report_permissions, 7)
    assert not can_view_credit_changes(no_report_permissions, 7)

    restricted_reports = AdminPrincipal(
        7, "operator", None,
        AdminPermissionSet({
            "SEE CONNECTION LOGS": "Restricted",
            "SEE CREDIT CHANGES": "Restricted",
        }),
    )
    assert can_view_connection_logs(restricted_reports, 7)
    assert not can_view_connection_logs(restricted_reports, 8)
    assert can_view_credit_changes(restricted_reports, 7)
    assert not can_view_credit_changes(restricted_reports, 8)

    all_reports = AdminPrincipal(
        7, "operator", None,
        AdminPermissionSet({
            "SEE CONNECTION LOGS": "All",
            "SEE CREDIT CHANGES": "All",
        }),
    )
    assert can_view_connection_logs(all_reports, 8)
    assert can_view_credit_changes(all_reports, 8)

    god = AdminPrincipal(7, "operator", None, AdminPermissionSet({"GOD": ""}))
    assert can_view_connection_logs(god, 8)
    assert can_view_credit_changes(god, 8)

def test_change_user_credit_requires_get_information_and_owner_scope():
    from atd_radius.api.admin_dependencies import AdminPrincipal, can_change_user_credit
    from atd_radius.domain.admin_permissions import AdminPermissionSet

    restricted = AdminPrincipal(
        7, "operator", None,
        AdminPermissionSet({
            "GET USER INFORMATION": "Restricted",
            "CHANGE USER CREDIT": "Restricted",
        }),
    )
    assert can_change_user_credit(restricted, 7)
    assert not can_change_user_credit(restricted, 8)

    missing_dependency = AdminPrincipal(
        7, "operator", None,
        AdminPermissionSet({"CHANGE USER CREDIT": "All"}),
    )
    assert not can_change_user_credit(missing_dependency, 7)

    all_users = AdminPrincipal(
        7, "operator", None,
        AdminPermissionSet({
            "GET USER INFORMATION": "All",
            "CHANGE USER CREDIT": "All",
        }),
    )
    assert can_change_user_credit(all_users, 8)

    god = AdminPrincipal(7, "operator", None, AdminPermissionSet({"GOD": ""}))
    assert can_change_user_credit(god, 8)

