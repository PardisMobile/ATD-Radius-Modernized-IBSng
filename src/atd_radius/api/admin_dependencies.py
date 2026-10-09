"""Reusable native admin-session and source-backed permission dependencies."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request

from atd_radius.domain.admin_permissions import (
    AdminPermissionEvaluator,
    AdminPermissionSet,
    PermissionKind,
    PermissionSpec,
)
from atd_radius.infrastructure.admin_repository import AdminLockedError, AdminRepository
from atd_radius.infrastructure.admin_sessions import AdminSessionRepository
from atd_radius.infrastructure.db import connection


@dataclass(frozen=True)
class AdminPrincipal:
    admin_id: int
    username: str
    remote_addr: str | None
    permissions: AdminPermissionSet


def _change_group_allowed(value: str | None, context: dict[str, object]) -> bool:
    if value == "All":
        return bool(context.get("can_use_group"))
    if value == "Restricted":
        return context.get("owner_id") == context.get("admin_id")
    return False


_GROUP_PERMISSIONS = AdminPermissionEvaluator(
    [
        PermissionSpec("GOD", PermissionKind.NO_VALUE),
        PermissionSpec("ADD NEW GROUP", PermissionKind.NO_VALUE),
        PermissionSpec("ACCESS ALL GROUPS", PermissionKind.NO_VALUE),
        PermissionSpec("GROUP ACCESS", PermissionKind.MULTI_VALUE),
        PermissionSpec(
            "CHANGE GROUP",
            PermissionKind.CONTEXTUAL,
            dependencies=("ADD NEW GROUP",),
            evaluator=_change_group_allowed,
        ),
    ]
)


def _all_or_owner(value: str | None, context: dict[str, object]) -> bool:
    return value == "All" or (
        value == "Restricted" and context.get("owner_id") == context.get("admin_id")
    )


_USER_PERMISSIONS = AdminPermissionEvaluator(
    [
        PermissionSpec("GOD", PermissionKind.NO_VALUE),
        PermissionSpec("ADD NEW USER", PermissionKind.NO_VALUE),
        PermissionSpec("GET USER INFORMATION", PermissionKind.CONTEXTUAL, evaluator=_all_or_owner),
        PermissionSpec(
            "CHANGE USER ATTRIBUTES",
            PermissionKind.CONTEXTUAL,
            dependencies=("GET USER INFORMATION",),
            evaluator=_all_or_owner,
        ),
        PermissionSpec(
            "DELETE USER",
            PermissionKind.CONTEXTUAL,
            dependencies=("GET USER INFORMATION",),
            evaluator=_all_or_owner,
        ),
    ]
)


_RAS_PERMISSIONS = AdminPermissionEvaluator(
    [
        PermissionSpec("GOD", PermissionKind.NO_VALUE),
        PermissionSpec("LIST RAS", PermissionKind.NO_VALUE),
        PermissionSpec(
            "GET RAS INFORMATION",
            PermissionKind.NO_VALUE,
            dependencies=("LIST RAS",),
        ),
        PermissionSpec(
            "CHANGE RAS",
            PermissionKind.NO_VALUE,
            dependencies=("LIST RAS", "GET RAS INFORMATION"),
        ),
    ]
)


def require_admin_session(
    request: Request,
    x_admin_session: str | None = Header(default=None, alias="X-Admin-Session"),
) -> AdminPrincipal:
    if not x_admin_session:
        raise HTTPException(status_code=401, detail="Administrator session required")
    with connection() as conn:
        session = AdminSessionRepository(conn).get_active(x_admin_session)
        if session is None:
            raise HTTPException(status_code=401, detail="Administrator session is invalid or expired")
        admin_repo = AdminRepository(conn)
        try:
            admin_repo.require_unlocked(session.admin_id)
        except AdminLockedError as exc:
            raise HTTPException(status_code=403, detail="Administrator is locked") from exc
        permissions = admin_repo.permissions(session.admin_id)
        remote_addr = request.client.host if request.client is not None else None
        return AdminPrincipal(session.admin_id, session.username, remote_addr, permissions)


def require_admin_permission(permission_name: str):
    """Create a dependency enforcing a session and a source-backed permission."""
    def dependency(
        principal: AdminPrincipal = Depends(require_admin_session),
    ) -> AdminPrincipal:
        if permission_name in {"LIST RAS", "GET RAS INFORMATION", "CHANGE RAS"}:
            evaluator = _RAS_PERMISSIONS
        elif permission_name in {"ADD NEW USER", "GET USER INFORMATION", "CHANGE USER ATTRIBUTES", "DELETE USER"}:
            evaluator = _USER_PERMISSIONS
        else:
            evaluator = _GROUP_PERMISSIONS
        if not evaluator.can_do(principal.permissions, permission_name):
            raise HTTPException(status_code=403, detail="Administrator permission denied")
        return principal

    dependency.__name__ = f"require_admin_{permission_name.lower().replace(' ', '_')}"
    return dependency


def can_access_user(principal: AdminPrincipal, owner_id: int | None) -> bool:
    return _USER_PERMISSIONS.can_do(
        principal.permissions,
        "GET USER INFORMATION",
        context={"admin_id": principal.admin_id, "owner_id": owner_id},
    )


def can_change_user(principal: AdminPrincipal, owner_id: int | None) -> bool:
    return _USER_PERMISSIONS.can_do(
        principal.permissions,
        "CHANGE USER ATTRIBUTES",
        context={"admin_id": principal.admin_id, "owner_id": owner_id},
    )


def can_delete_user(principal: AdminPrincipal, owner_id: int | None) -> bool:
    return _USER_PERMISSIONS.can_do(
        principal.permissions,
        "DELETE USER",
        context={"admin_id": principal.admin_id, "owner_id": owner_id},
    )


def require_group_change():
    """Create a dependency that checks CHANGE GROUP against the target group's owner/access."""
    def dependency(
        group_id: int,
        principal: AdminPrincipal = Depends(require_admin_session),
    ) -> AdminPrincipal:
        from atd_radius.infrastructure.group import GroupRepository

        with connection() as conn:
            group = GroupRepository(conn).get(group_id)
        if group is None:
            raise HTTPException(status_code=404, detail="group not found")
        context = {
            "admin_id": principal.admin_id,
            "owner_id": group.owner_id,
            "can_use_group": can_use_group(principal, group.name, group.owner_id),
        }
        if not _GROUP_PERMISSIONS.can_do(
            principal.permissions, "CHANGE GROUP", context=context
        ):
            raise HTTPException(status_code=403, detail="Administrator permission denied")
        return principal

    dependency.__name__ = "require_change_group"
    return dependency


def can_use_group(principal: AdminPrincipal, group_name: str, owner_id: int | None) -> bool:
    """Match A1.24 Admin.canUseGroup for already-loaded group data."""
    if principal.permissions.is_god() or principal.permissions.has_perm("ACCESS ALL GROUPS"):
        return True
    if owner_id == principal.admin_id:
        return True
    value = principal.permissions.values.get("GROUP ACCESS")
    return bool(value) and group_name in value.split(",")


__all__ = [
    "AdminPrincipal",
    "can_use_group",
    "can_access_user",
    "can_change_user",
    "can_delete_user",
    "require_admin_permission",
    "require_admin_session",
    "require_group_change",
]
