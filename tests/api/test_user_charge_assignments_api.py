from atd_radius.api.admin_dependencies import AdminPrincipal, can_use_charge
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.api.users import _charge_attribute_access


def test_can_use_charge_matches_a124_visibility_access_all_and_multi_value_access():
    visible = AdminPrincipal(7, "operator", None, AdminPermissionSet({}))
    assert can_use_charge(visible, "PublicPlan", True)

    all_access = AdminPrincipal(7, "operator", None, AdminPermissionSet({
        "ACCESS ALL CHARGES": "",
    }))
    assert can_use_charge(all_access, "PrivatePlan", False)

    selected = AdminPrincipal(7, "operator", None, AdminPermissionSet({
        "CHARGE ACCESS": "Gold,PrivatePlan",
    }))
    assert can_use_charge(selected, "PrivatePlan", False)
    assert not can_use_charge(selected, "OtherPlan", False)


def test_user_charge_attribute_permission_distinguishes_internet_and_voip():
    normal = AdminPrincipal(7, "operator", None, AdminPermissionSet({
        "GET USER INFORMATION": "All",
        "CHANGE USER ATTRIBUTES": "All",
    }))
    voip = AdminPrincipal(7, "operator", None, AdminPermissionSet({
        "GET USER INFORMATION": "All",
        "CHANGE USER ATTRIBUTES": "All",
        "CHANGE VOIP USER ATTRIBUTES": "All",
    }))
    assert _charge_attribute_access(normal, 9, "normal_charge")
    assert not _charge_attribute_access(normal, 9, "voip_charge")
    assert _charge_attribute_access(voip, 9, "voip_charge")
