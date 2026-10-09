"""Reusable native admin-session and source-backed permission dependencies."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from atd_radius.domain.admin_permissions import (
    AdminPermissionEvaluator,
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


def require_admin_permission(permission_name: str):
    """Create a dependency enforcing a session, current lock state, and A1.24 permission."""
    def dependency(
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
            if not _RAS_PERMISSIONS.can_do(permissions, permission_name):
                raise HTTPException(status_code=403, detail="Administrator permission denied")
            remote_addr = request.client.host if request.client is not None else None
            return AdminPrincipal(session.admin_id, session.username, remote_addr)

    dependency.__name__ = f"require_admin_{permission_name.lower().replace(' ', '_')}"
    return dependency
