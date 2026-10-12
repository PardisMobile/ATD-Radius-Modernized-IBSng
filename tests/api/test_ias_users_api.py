from decimal import Decimal

import pytest
from fastapi import HTTPException

import atd_radius.api.ias_users as api
from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.domain.admin_permissions import AdminPermissionSet


def principal(perms):
    return AdminPrincipal(7, "operator", None, AdminPermissionSet(perms))


def test_ias_user_info_is_god_only_when_source_permission_is_unregistered():
    require = require_admin_permission("GOD")
    assert require(principal({"GOD": ""})).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"HANDLE IAS EVENTS": ""}))
    assert denied.value.status_code == 403


def test_ias_user_info_view_preserves_native_keys():
    view = api.IASUserInfoView(
        user_id=1, owner="root", credit=Decimal("4.50"),
        normal_username="alice", voip_username=None,
    )
    assert view.owner == "root"
    assert view.credit == Decimal("4.50")
    assert view.normal_username == "alice"
    assert view.voip_username is None


def test_ias_user_info_maps_invalid_ids_to_422(monkeypatch):
    class Repository:
        def __init__(self, _conn): pass
        def get_many(self, _ids):
            raise ValueError("user IDs must be positive integers")
    from contextlib import contextmanager
    @contextmanager
    def fake_connection():
        yield object()
    monkeypatch.setattr(api, "connection", fake_connection)
    monkeypatch.setattr(api, "PostgresIASUserInfoRepository", Repository)
    with pytest.raises(HTTPException) as error:
        api.get_ias_user_info([0], principal({"GOD": ""}))
    assert error.value.status_code == 422
