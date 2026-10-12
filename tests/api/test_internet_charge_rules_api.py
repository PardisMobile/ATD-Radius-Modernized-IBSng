from decimal import Decimal

import pytest
from fastapi import HTTPException

import atd_radius.api.internet_charge_rules as api
from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.billing_rules import (
    InternetChargeNotFound,
    InternetChargeTypeError,
    InternetRuleConflictError,
    InternetRuleInputError,
)


def principal(perms):
    return AdminPrincipal(7, "operator", None, AdminPermissionSet(perms))


def test_change_charge_dependency_is_required_for_internet_rule_mutations():
    require = require_admin_permission("CHANGE CHARGE")
    assert require(principal({"ACCESS ALL CHARGES": "", "CHANGE CHARGE": ""})).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"ACCESS ALL CHARGES": ""}))
    assert denied.value.status_code == 403


def test_source_internet_rule_payload_keeps_native_charge_and_leaf_fields():
    payload = api.InternetChargeRulePayload(
        charge_name="Broadband",
        start_time="8",
        end_time="18",
        day_of_weeks=["Monday", "Tuesday"],
        cpm=Decimal("2.50"),
        cpk=Decimal("0.25"),
        assumed_kps=128,
        bandwidth_limit_kbytes=4096,
        tx_leaf_name="tx",
        rx_leaf_name="rx",
        ports=["_ALL_"],
    )
    converted = api._input(payload)
    assert converted.days == ("Monday", "Tuesday")
    assert converted.tx_leaf_name == "tx"
    assert converted.rx_leaf_name == "rx"
    assert converted.bandwidth_limit_kbytes == 4096


def test_internet_rule_errors_map_to_native_api_statuses():
    assert api._mutation_error(InternetChargeNotFound("missing")).status_code == 404
    assert api._mutation_error(InternetChargeTypeError("wrong type")).status_code == 422
    assert api._mutation_error(InternetRuleConflictError("overlap")).status_code == 409
    assert api._mutation_error(InternetRuleInputError("bad input")).status_code == 422


def test_rule_list_uses_source_charge_visibility_scope():
    import inspect
    source = inspect.getsource(api.list_internet_charge_rules)
    assert "accessible_charge_ids" in source
    assert "require_admin_session" in source
