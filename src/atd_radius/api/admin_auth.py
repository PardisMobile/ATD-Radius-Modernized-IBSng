from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from atd_radius.application.admin_authentication import (
    AdminAddressDeniedError,
    AdminAuthenticationError,
    AdminAuthenticator,
)
from atd_radius.config import settings
from atd_radius.infrastructure.admin_repository import AdminLockedError, AdminRepository
from atd_radius.infrastructure.admin_sessions import AdminSessionRepository
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository

router = APIRouter(prefix="/admin", tags=["ADMIN AUTH"])


class AdminLoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


class AdminLoginView(BaseModel):
    access_token: str
    token_type: str = "AdminSession"
    expires_at: str


class AdminSessionView(BaseModel):
    admin_id: int
    username: str
    expires_at: str
    remote_addr: str | None


def _remote_addr(request: Request) -> str | None:
    # Do not trust X-Forwarded-For until trusted-proxy configuration exists.
    return request.client.host if request.client is not None else None


@router.post("/login", response_model=AdminLoginView)
def admin_login(payload: AdminLoginPayload, request: Request) -> AdminLoginView:
    remote_addr = _remote_addr(request)
    try:
        with connection() as conn:
            admin_repo = AdminRepository(conn)
            admin = AdminAuthenticator(admin_repo).authenticate(
                payload.username, payload.password, remote_addr or ""
            )
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=max(60, settings.admin_session_ttl_seconds)
            )
            session_id = AdminSessionRepository(conn).create(
                token=token,
                admin_id=admin.admin_id,
                expires_at=expires_at,
                remote_addr=remote_addr,
            )
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="admin.login",
                outcome="success",
                target_type="admin_session",
                target_id=str(session_id),
                remote_addr=remote_addr,
                details={"session_id": session_id},
            )
            conn.commit()
    except AdminAuthenticationError as exc:
        raise HTTPException(status_code=401, detail="Invalid administrator credentials") from exc
    except AdminAddressDeniedError as exc:
        raise HTTPException(status_code=403, detail="Administrator login address denied") from exc
    except AdminLockedError as exc:
        raise HTTPException(status_code=403, detail="Administrator is locked") from exc

    return AdminLoginView(access_token=token, expires_at=expires_at.isoformat())


@router.get("/session", response_model=AdminSessionView)
def admin_session(
    x_admin_session: str | None = Header(default=None, alias="X-Admin-Session"),
) -> AdminSessionView:
    if not x_admin_session:
        raise HTTPException(status_code=401, detail="Administrator session required")
    with connection() as conn:
        session = AdminSessionRepository(conn).get_active(x_admin_session)
        if session is None:
            raise HTTPException(status_code=401, detail="Administrator session is invalid or expired")
        try:
            AdminRepository(conn).require_unlocked(session.admin_id)
        except AdminLockedError as exc:
            raise HTTPException(status_code=403, detail="Administrator is locked") from exc
        return AdminSessionView(
            admin_id=session.admin_id,
            username=session.username,
            expires_at=session.expires_at.isoformat(),
            remote_addr=session.remote_addr,
        )


@router.delete("/session", status_code=204)
def admin_logout(
    x_admin_session: str | None = Header(default=None, alias="X-Admin-Session"),
) -> Response:
    if not x_admin_session:
        raise HTTPException(status_code=401, detail="Administrator session required")
    with connection() as conn:
        session_repo = AdminSessionRepository(conn)
        session = session_repo.get_active(x_admin_session)
        if session is None:
            raise HTTPException(status_code=401, detail="Administrator session is invalid or expired")
        OperationalAuditRepository(conn).append(
            actor_admin_id=session.admin_id,
            actor_username=session.username,
            action="admin.logout",
            outcome="success",
            target_type="admin_session",
            target_id=str(session.session_id),
            remote_addr=session.remote_addr,
            details={"session_id": session.session_id},
        )
        session_repo.revoke(x_admin_session)
        conn.commit()
    return Response(status_code=204)
