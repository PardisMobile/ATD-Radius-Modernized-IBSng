"""Transactional native IBSng A1.24 administrator permission mutations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from atd_radius.domain.admin_permission_catalog import (
    PermissionKind,
    permission_definition,
    validate_permission_value,
)


class AdminPermissionMutationConnection(Protocol):
    def execute(self, sql: str, params=()): ...


class AdminPermissionMutationError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class AdminPermissionMutationResult:
    admin_id: int
    username: str
    permissions: tuple[tuple[str, str | None], ...]


class AdminPermissionMutationRepository:
    """Mutate native admin_perms under a lock on the owning admin row."""

    def __init__(self, conn: AdminPermissionMutationConnection) -> None:
        self.conn = conn

    def add_or_change(self, username: str, permission_name: str, value: str) -> AdminPermissionMutationResult:
        admin_id = self._lock_admin(username)
        definition = permission_definition(permission_name)
        if definition is None:
            raise AdminPermissionMutationError("unknown_permission")

        try:
            validate_permission_value(
                permission_name,
                value,
                group_exists=self._group_exists,
                charge_exists=self._charge_exists,
            )
        except ValueError as exc:
            raise AdminPermissionMutationError("invalid_value") from exc

        current = self._permission_map(admin_id)
        if permission_name not in current:
            if any(dependency not in current for dependency in definition.dependencies):
                raise AdminPermissionMutationError("dependency_not_satisfied")
            self.conn.execute(
                """
                INSERT INTO admin_perms (admin_id, perm_name, perm_value)
                VALUES (%s, %s, %s)
                """,
                (admin_id, permission_name, value),
            )
        elif definition.kind is PermissionKind.NO_VALUE:
            raise AdminPermissionMutationError("already_has_permission")
        elif definition.kind is PermissionKind.MULTI_VALUE:
            old_value = current[permission_name] or ""
            values = [] if not old_value else old_value.split(",")
            if value in values:
                raise AdminPermissionMutationError("duplicate_value")
            new_value = ",".join([*values, value])
            self.conn.execute(
                """
                UPDATE admin_perms SET perm_value = %s
                WHERE admin_id = %s AND perm_name = %s
                """,
                (new_value, admin_id, permission_name),
            )
        else:
            self.conn.execute(
                """
                UPDATE admin_perms SET perm_value = %s
                WHERE admin_id = %s AND perm_name = %s
                """,
                (value, admin_id, permission_name),
            )

        return self._result(admin_id, username)

    def delete_permission(self, username: str, permission_name: str) -> AdminPermissionMutationResult:
        admin_id = self._lock_admin(username)
        if permission_definition(permission_name) is None:
            raise AdminPermissionMutationError("unknown_permission")
        current = self._permission_map(admin_id)
        if permission_name not in current:
            raise AdminPermissionMutationError("permission_not_assigned")

        for assigned_name in current:
            assigned = permission_definition(assigned_name)
            if assigned is not None and permission_name in assigned.dependencies:
                raise AdminPermissionMutationError("dependent_permission")

        self.conn.execute(
            "DELETE FROM admin_perms WHERE admin_id = %s AND perm_name = %s",
            (admin_id, permission_name),
        )
        return self._result(admin_id, username)

    def delete_multi_value(
        self, username: str, permission_name: str, value: str
    ) -> AdminPermissionMutationResult:
        admin_id = self._lock_admin(username)
        definition = permission_definition(permission_name)
        if definition is None:
            raise AdminPermissionMutationError("unknown_permission")
        current = self._permission_map(admin_id)
        if permission_name not in current:
            raise AdminPermissionMutationError("permission_not_assigned")
        if definition.kind is not PermissionKind.MULTI_VALUE:
            raise AdminPermissionMutationError("not_multi_value")

        old_value = current[permission_name] or ""
        values = [] if not old_value else old_value.split(",")
        try:
            values.pop(values.index(value))
        except ValueError as exc:
            raise AdminPermissionMutationError("value_not_assigned") from exc

        # A1.24 updates the raw value after removing the first matching item.
        # ATD scopes the UPDATE by admin_id as well as perm_name; the legacy
        # source query omits admin_id here and could alter other admins' rows.
        self.conn.execute(
            """
            UPDATE admin_perms SET perm_value = %s
            WHERE admin_id = %s AND perm_name = %s
            """,
            (",".join(values), admin_id, permission_name),
        )
        return self._result(admin_id, username)

    def _lock_admin(self, username: str) -> int:
        row = self.conn.execute(
            "SELECT admin_id FROM admins WHERE username = %s FOR UPDATE",
            (username,),
        ).fetchone()
        if row is None:
            raise AdminPermissionMutationError("admin_not_found")
        return int(row[0])

    def _permission_map(self, admin_id: int) -> dict[str, str | None]:
        rows = self.conn.execute(
            "SELECT perm_name, perm_value FROM admin_perms WHERE admin_id = %s ORDER BY perm_name",
            (admin_id,),
        ).fetchall()
        return {
            str(name): str(value) if value is not None else None
            for name, value in rows
        }

    def _result(self, admin_id: int, username: str) -> AdminPermissionMutationResult:
        return AdminPermissionMutationResult(
            admin_id=admin_id,
            username=username,
            permissions=tuple(
                (name, value) for name, value in sorted(self._permission_map(admin_id).items())
            ),
        )

    def _group_exists(self, group_name: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM groups WHERE group_name = %s",
            (group_name,),
        ).fetchone() is not None

    def _charge_exists(self, charge_name: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM charges WHERE name = %s",
            (charge_name,),
        ).fetchone() is not None
