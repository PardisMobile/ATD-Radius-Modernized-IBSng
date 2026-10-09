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
        if not _RAS_PERMISSIONS.can_do(principal.permissions, permission_name):
            raise HTTPException(status_code=403, detail="Administrator permission denied")
        return principal

    dependency.__name__ = f"require_admin_{permission_name.lower().replace(' ', '_')}"
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
    "require_admin_permission",
    "require_admin_session",
]
