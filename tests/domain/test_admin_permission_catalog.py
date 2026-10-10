from atd_radius.domain.admin_permission_catalog import (
    PermissionKind,
    all_permission_definitions,
    permission_definition,
    validate_permission_value,
)


def test_catalog_covers_all_51_source_permission_names():
    definitions = all_permission_definitions()
    assert len(definitions) == 51
    assert len({item.name for item in definitions}) == 51


def test_source_dependencies_for_admin_permission_management():
    assert permission_definition("SEE ADMIN PERMISSIONS").dependencies == ("SEE ADMIN INFO",)
    assert permission_definition("CHANGE ADMIN PERMISSIONS").dependencies == (
        "SEE ADMIN INFO", "SEE ADMIN PERMISSIONS"
    )
    assert permission_definition("CHANGE ADMIN DEPOSIT").dependencies == ("CHANGE ADMIN INFO",)


def test_single_value_permissions_accept_only_source_candidates():
    exists = lambda _name: True
    validate_permission_value(
        "CHANGE USER CREDIT", "All", group_exists=exists, charge_exists=exists
    )
    validate_permission_value(
        "CHANGE USER CREDIT", "Restricted", group_exists=exists, charge_exists=exists
    )
    try:
        validate_permission_value(
            "CHANGE USER CREDIT", "all", group_exists=exists, charge_exists=exists
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid All/Restricted value was accepted")


def test_resource_and_ip_multivalue_validation():
    validate_permission_value(
        "GROUP ACCESS", "staff", group_exists=lambda name: name == "staff", charge_exists=lambda _: False
    )
    for permission, value in (("GROUP ACCESS", "missing"), ("CHARGE ACCESS", "missing"), ("LIMIT LOGIN ADDR", "999.1.1.1")):
        try:
            validate_permission_value(
                permission, value, group_exists=lambda _: False, charge_exists=lambda _: False
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"{permission} accepted invalid value {value}")


def test_no_value_permission_uses_presence_not_value_semantics():
    spec = permission_definition("DELETE ADMIN")
    assert spec.kind is PermissionKind.NO_VALUE
    validate_permission_value(
        "DELETE ADMIN", "legacy-inert-value", group_exists=lambda _: False, charge_exists=lambda _: False
    )
