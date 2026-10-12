import pytest
from fastapi import HTTPException

import atd_radius.api.ias_events as api
from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.domain.admin_permissions import AdminPermissionSet


def principal(perms):
    return AdminPrincipal(7, "operator", None, AdminPermissionSet(perms))


def test_ias_events_require_native_handle_ias_events_permission():
    require = require_admin_permission("HANDLE IAS EVENTS")
    assert require(principal({"HANDLE IAS EVENTS": ""})).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"ACCESS ALL CHARGES": ""}))
    assert denied.value.status_code == 403


def test_ias_event_view_exposes_source_event_type_name():
    from datetime import datetime
    from decimal import Decimal
    from atd_radius.infrastructure.ias_events_repository import IASEvent

    event = IASEvent(5, 1, datetime(2026, 10, 12), "admin", Decimal("10"), "1", "note")
    view = api._view(event)
    assert view.event_type_name == "CHANGE_CREDIT"
    assert view.actor == "admin"
