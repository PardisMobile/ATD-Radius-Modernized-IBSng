import pytest

from atd_radius.infrastructure.admin_permission_mutations import (
    AdminPermissionMutationError,
    AdminPermissionMutationRepository,
)


class Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, *, admins=None, permissions=None, groups=None, charges=None):
        self.admins = admins or {"operator": 7, "target": 8, "other": 9}
        self.permissions = {key: dict(value) for key, value in (permissions or {}).items()}
        self.groups = set(groups or ())
        self.charges = set(charges or ())
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT admin_id FROM admins WHERE username = %s FOR UPDATE" in sql:
            return Result((self.admins[params[0]],) if params[0] in self.admins else None)
        if "SELECT perm_name, perm_value FROM admin_perms WHERE admin_id = %s ORDER BY perm_name" in sql:
            rows = sorted(self.permissions.get(params[0], {}).items())
            return Result(rows=rows)
        if "SELECT 1 FROM groups WHERE group_name = %s" in sql:
            return Result((1,) if params[0] in self.groups else None)
        if "SELECT 1 FROM charges WHERE name = %s" in sql:
            return Result((1,) if params[0] in self.charges else None)
        if "INSERT INTO admin_perms" in sql:
            admin_id, name, value = params
            self.permissions.setdefault(admin_id, {})[name] = value
            return Result()
        if "UPDATE admin_perms SET perm_value = %s" in sql:
            value, admin_id, name = params
            self.permissions.setdefault(admin_id, {})[name] = value
            return Result()
        if "DELETE FROM admin_perms WHERE admin_id = %s AND perm_name = %s" in sql:
            admin_id, name = params
            self.permissions.setdefault(admin_id, {}).pop(name, None)
            return Result()
        raise AssertionError(f"unhandled SQL: {sql}")


def test_add_permission_requires_source_dependencies_and_persists_native_row():
    conn = Connection(permissions={8: {"SEE ADMIN INFO": ""}})
    repo = AdminPermissionMutationRepository(conn)
    with pytest.raises(AdminPermissionMutationError) as error:
        repo.add_or_change("target", "CHANGE ADMIN PERMISSIONS", "")
    assert error.value.code == "dependency_not_satisfied"

    conn.permissions[8]["SEE ADMIN PERMISSIONS"] = ""
    result = repo.add_or_change("target", "CHANGE ADMIN PERMISSIONS", "")
    assert result.admin_id == 8
    assert ("CHANGE ADMIN PERMISSIONS", "") in result.permissions


def test_single_value_permission_updates_existing_value():
    conn = Connection(permissions={8: {"GET USER INFORMATION": "Restricted"}})
    result = AdminPermissionMutationRepository(conn).add_or_change("target", "GET USER INFORMATION", "All")
    assert ("GET USER INFORMATION", "All") in result.permissions


def test_multivalue_permission_appends_without_duplicates_and_removes_scoped_value():
    conn = Connection(permissions={8: {"GROUP ACCESS": "staff"}, 9: {"GROUP ACCESS": "staff"}} , groups={"staff", "sales"})
    repo = AdminPermissionMutationRepository(conn)
    result = repo.add_or_change("target", "GROUP ACCESS", "sales")
    assert ("GROUP ACCESS", "staff,sales") in result.permissions

    with pytest.raises(AdminPermissionMutationError) as duplicate:
        repo.add_or_change("target", "GROUP ACCESS", "sales")
    assert duplicate.value.code == "duplicate_value"

    repo.delete_multi_value("target", "GROUP ACCESS", "staff")
    assert conn.permissions[8]["GROUP ACCESS"] == "sales"
    assert conn.permissions[9]["GROUP ACCESS"] == "staff"


def test_delete_permission_blocks_removing_dependency_and_deletes_scoped_row():
    conn = Connection(permissions={8: {"SEE ADMIN INFO": "", "CHANGE ADMIN INFO": ""}, 9: {"SEE ADMIN INFO": ""}})
    repo = AdminPermissionMutationRepository(conn)
    with pytest.raises(AdminPermissionMutationError) as dependent:
        repo.delete_permission("target", "SEE ADMIN INFO")
    assert dependent.value.code == "dependent_permission"

    result = repo.delete_permission("target", "CHANGE ADMIN INFO")
    assert "CHANGE ADMIN INFO" not in dict(result.permissions)
    assert conn.permissions[9]["SEE ADMIN INFO"] == ""


def test_unknown_admin_and_permission_fail_closed():
    repo = AdminPermissionMutationRepository(Connection())
    with pytest.raises(AdminPermissionMutationError) as missing:
        repo.add_or_change("absent", "GOD", "")
    assert missing.value.code == "admin_not_found"
    with pytest.raises(AdminPermissionMutationError) as unknown:
        repo.add_or_change("target", "MADE UP PERMISSION", "")
    assert unknown.value.code == "unknown_permission"


def test_delete_multi_value_requires_multi_permission_and_existing_value():
    repo = AdminPermissionMutationRepository(Connection(permissions={8: {"GOD": ""}}))
    with pytest.raises(AdminPermissionMutationError) as wrong_kind:
        repo.delete_multi_value("target", "GOD", "x")
    assert wrong_kind.value.code == "not_multi_value"
