from atd_radius.domain.admin_permissions import (
    AdminPermissionEvaluator,
    AdminPermissionSet,
    PermissionKind,
    PermissionSpec,
    parse_permission_value,
)


def evaluator():
    return AdminPermissionEvaluator([
        PermissionSpec("GOD", PermissionKind.NO_VALUE),
        PermissionSpec("SEE ONLINE USERS", PermissionKind.NO_VALUE),
        PermissionSpec("KILL USER", PermissionKind.SINGLE_VALUE, dependencies=("SEE ONLINE USERS",)),
        PermissionSpec("RAS SCOPE", PermissionKind.MULTI_VALUE),
        PermissionSpec("CONTEXT", PermissionKind.CONTEXTUAL, evaluator=lambda value, ctx: value == ctx.get("scope")),
    ])


def test_has_perm_checks_presence_not_permission_value():
    permissions = AdminPermissionSet({"KILL USER": "", "SEE ONLINE USERS": ""})
    auth = evaluator()
    assert permissions.has_perm("KILL USER")
    assert not auth.check_perm(permissions, "KILL USER", requested_value="user-1")
    assert not auth.check_perm(permissions, "UNKNOWN", requested_value="user-1")


def test_kill_user_dependency_is_enforced():
    auth = evaluator()
    without_dependency = AdminPermissionSet({"KILL USER": "user-1"})
    with_dependency = AdminPermissionSet({"KILL USER": "user-1", "SEE ONLINE USERS": ""})
    assert not auth.check_perm(without_dependency, "KILL USER", requested_value="user-1")
    assert auth.check_perm(with_dependency, "KILL USER", requested_value="user-1")
    assert not auth.check_perm(with_dependency, "KILL USER", requested_value="user-2")


def test_god_bypass_applies_to_can_do_but_not_check_perm():
    auth = evaluator()
    permissions = AdminPermissionSet({"GOD": ""})
    assert permissions.is_god()
    assert not auth.check_perm(permissions, "UNREGISTERED")
    assert auth.can_do(permissions, "UNREGISTERED")


def test_multi_value_and_contextual_rules_are_explicit():
    auth = evaluator()
    permissions = AdminPermissionSet({"RAS SCOPE": "ras-a,ras-b", "CONTEXT": "site-a"})
    assert auth.check_perm(permissions, "RAS SCOPE", requested_value="ras-b")
    assert not auth.check_perm(permissions, "RAS SCOPE", requested_value="ras-c")
    assert auth.check_perm(permissions, "CONTEXT", context={"scope": "site-a"})
    assert not auth.check_perm(permissions, "CONTEXT", context={"scope": "site-b"})


def test_permission_value_parser_preserves_native_text_semantics():
    assert parse_permission_value(PermissionKind.MULTI_VALUE, "") == []
    assert parse_permission_value(PermissionKind.MULTI_VALUE, "a,b") == ["a", "b"]
    assert parse_permission_value(PermissionKind.SINGLE_VALUE, "") == ""


def test_dependency_cycles_fail_closed():
    auth = AdminPermissionEvaluator([
        PermissionSpec("A", PermissionKind.NO_VALUE, dependencies=("B",)),
        PermissionSpec("B", PermissionKind.NO_VALUE, dependencies=("A",)),
    ])
    assert not auth.check_perm(AdminPermissionSet({"A": "", "B": ""}), "A")
