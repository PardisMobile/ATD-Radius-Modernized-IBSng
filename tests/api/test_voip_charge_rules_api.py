import pytest
from fastapi import HTTPException

import atd_radius.api.voip_charge_rules as api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet


def principal(perms):
    return AdminPrincipal(7, "operator", None, AdminPermissionSet(perms))


def test_charge_permission_dependency_is_required_for_mutation():
    from atd_radius.api.admin_dependencies import require_admin_permission
    require = require_admin_permission("CHANGE CHARGE")
    assert require(principal({"ACCESS ALL CHARGES": "", "CHANGE CHARGE": ""})).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"ACCESS ALL CHARGES": ""}))
    assert denied.value.status_code == 403


def test_mutation_error_maps_overlap_and_invalid_input():
    from atd_radius.infrastructure.voip_charge_rules import VoipRuleConflictError, VoipRuleInputError
    assert api._raise_mutation_error(VoipRuleConflictError("overlap")).status_code == 409
    assert api._raise_mutation_error(VoipRuleInputError("bad")).status_code == 422


def test_payload_preserves_native_day_names_and_wildcard_port():
    payload = api.VoipChargeRulePayload(
        charge_name="Calls", start_time="8", end_time="18",
        days=["Monday"], tariff_name="Business", ports=["_ALL_"],
    )
    converted = api._payload(payload)
    assert converted.days == ("Monday",)
    assert converted.ports == ("_ALL_",)
