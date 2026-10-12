from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.charges as api
from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.charges import ChargeAlreadyExists, ChargeInUseError, ChargeInputError, ChargeNotFound


def principal(perms):
    return AdminPrincipal(7, "operator", None, AdminPermissionSet(perms))


def test_charge_mutation_requires_native_change_charge_dependency():
    require = require_admin_permission("CHANGE CHARGE")
    assert require(principal({"ACCESS ALL CHARGES": "", "CHANGE CHARGE": ""})).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"ACCESS ALL CHARGES": ""}))
    assert denied.value.status_code == 403


def test_charge_errors_map_to_api_statuses():
    assert api._error(ChargeNotFound("x")).status_code == 404
    assert api._error(ChargeAlreadyExists("x")).status_code == 409
    assert api._error(ChargeInUseError("used")).status_code == 409
    assert api._error(ChargeInputError("bad")).status_code == 422


def test_charge_view_preserves_native_charge_fields():
    view = api._view(SimpleNamespace(
        charge_id=12, name="broadband", comment="internet",
        charge_type="Internet", admin_id=7, visible_to_all=True,
    ))
    assert view.charge_name == "broadband"
    assert view.charge_type == "Internet"
    assert view.admin_id == 7
    assert view.visible_to_all is True


def test_charge_payload_validates_native_name_and_type():
    payload = api.ChargeCreatePayload(
        charge_name="broadband", comment="", charge_type="Internet", visible_to_all=True,
    )
    assert payload.charge_type == "Internet"
    with pytest.raises(ValueError):
        api.ChargeCreatePayload(charge_name="bad name", charge_type="Internet")
    with pytest.raises(ValueError):
        api.ChargeCreatePayload(charge_name="valid_name", charge_type="Unknown")


def test_charge_visibility_matches_native_can_use_charge_rules():
    from atd_radius.api.admin_dependencies import can_use_charge
    restricted = principal({"CHARGE ACCESS": "Allowed"})
    assert can_use_charge(restricted, "Allowed", False) is True
    assert can_use_charge(restricted, "Denied", False) is False
    assert can_use_charge(principal({}), "Public", True) is True
    assert can_use_charge(principal({"ACCESS ALL CHARGES": ""}), "Hidden", False) is True


def test_accessible_charge_ids_filters_and_enforces_requested_scope():
    from atd_radius.api.charges import accessible_charge_ids
    public = SimpleNamespace(charge_id=1, name="Public", visible_to_all=True)
    allowed = SimpleNamespace(charge_id=2, name="Allowed", visible_to_all=False)
    hidden = SimpleNamespace(charge_id=3, name="Hidden", visible_to_all=False)
    admin = principal({"CHARGE ACCESS": "Allowed"})
    assert accessible_charge_ids([public, allowed, hidden], admin, None) == [1, 2]
    assert accessible_charge_ids([public, allowed, hidden], admin, 2) == [2]
    with pytest.raises(HTTPException) as denied:
        accessible_charge_ids([public, allowed, hidden], admin, 3)
    assert denied.value.status_code == 403


def test_charge_list_filters_visible_and_explicitly_granted_charges(monkeypatch):
    from contextlib import contextmanager
    @contextmanager
    def fake_connection():
        yield object()
    monkeypatch.setattr(api, "connection", fake_connection)
    charges = [
        SimpleNamespace(charge_id=1, name="Public", comment="", charge_type="Internet", admin_id=7, visible_to_all=True),
        SimpleNamespace(charge_id=2, name="Allowed", comment="", charge_type="Internet", admin_id=7, visible_to_all=False),
        SimpleNamespace(charge_id=3, name="Hidden", comment="", charge_type="VoIP", admin_id=7, visible_to_all=False),
    ]
    monkeypatch.setattr(api.PostgresChargeRepository, "list", lambda self: charges)
    result = api.list_charges(admin=principal({"CHARGE ACCESS": "Allowed"}))
    assert [item.charge_name for item in result] == ["Public", "Allowed"]


def test_charge_detail_denies_non_visible_ungranted_charge(monkeypatch):
    from contextlib import contextmanager
    @contextmanager
    def fake_connection():
        yield object()
    monkeypatch.setattr(api, "connection", fake_connection)
    hidden = SimpleNamespace(charge_id=3, name="Hidden", comment="", charge_type="VoIP", admin_id=7, visible_to_all=False)
    monkeypatch.setattr(api.PostgresChargeRepository, "get_by_name", lambda self, name: hidden)
    with pytest.raises(HTTPException) as denied:
        api.get_charge("Hidden", admin=principal({"CHARGE ACCESS": "Allowed"}))
    assert denied.value.status_code == 403
