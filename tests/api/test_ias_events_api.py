import pytest
from fastapi import HTTPException

import atd_radius.api.ias_events as api
from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.domain.admin_permissions import AdminPermissionSet


def principal(perms):
    return AdminPrincipal(7, "operator", None, AdminPermissionSet(perms))


def test_ias_events_are_god_only_when_source_permission_is_unregistered():
    require = require_admin_permission("GOD")
    assert require(principal({"GOD": ""})).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"HANDLE IAS EVENTS": "", "ACCESS ALL CHARGES": ""}))
    assert denied.value.status_code == 403


def test_ias_event_view_exposes_source_event_type_name():
    from datetime import datetime
    from decimal import Decimal
    from atd_radius.infrastructure.ias_events_repository import IASEvent

    event = IASEvent(5, 1, datetime(2026, 10, 12), "admin", Decimal("10"), "1", "note")
    view = api._view(event)
    assert view.event_type_name == "CHANGE_CREDIT"
    assert view.actor == "admin"
