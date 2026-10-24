"""Admin-facing view and source-backed kill action for live RADIUS sessions."""
from __future__ import annotations

import ipaddress
import json
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import (
    AdminPrincipal,
    can_kill_user,
    can_clear_user,
    can_see_online_users,
    require_admin_session,
)
from atd_radius.domain.radius_runtime import SessionKey
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository

router = APIRouter(prefix="/online-sessions", tags=["ONLINE SESSIONS"])


class OnlineSessionView(BaseModel):
    user_id: int
    username: str | None
    ras_id: int
    unique_id: str
    started_at: str | None
    service: str
    remote_ip: str | None
    nas_port: str | None
    input_octets: int
    output_octets: int
    termination_requested: bool


class LoginInProgressView(BaseModel):
    user_id: int
    username: str
    ras_id: int
    created_at: str
    ras_multi_login_allowed: bool | None


class OnlineSessionsView(BaseModel):
    sessions: list[OnlineSessionView]
    login_in_progress: list[LoginInProgressView]


class KillOnlineSessionPayload(BaseModel):
    user_id: int = Field(gt=0)
    ras_id: int = Field(gt=0)
    unique_id: str = Field(min_length=1, max_length=255)


class KillOnlineSessionView(BaseModel):
    user_id: int
    ras_id: int
    unique_id: str
    termination_requested: bool
    note: str


class ClearOnlineSessionView(BaseModel):
    user_id: int
    ras_id: int
    unique_id: str
    cleared_locally: bool
    credit_deducted: bool
    ras_disconnect_sent: bool
    note: str


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    return dict(value) if isinstance(value, Mapping) else {}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


@router.get("", response_model=OnlineSessionsView)
def list_online_sessions(
    admin: AdminPrincipal = Depends(require_admin_session),
) -> OnlineSessionsView:
    # Restricted administrators can see their own category; this also distinguishes
    # "no sessions" from "no permission" when the result set is empty.
    if not can_see_online_users(admin, admin.admin_id):
        raise HTTPException(status_code=403, detail="SEE ONLINE USERS permission required")

    with connection() as conn:
        rows = conn.execute(
            """
            SELECT s.user_id, s.ras_id, s.unique_id, s.state, u.owner_id,
                   COALESCE(nu.normal_username, vu.voip_username)
            FROM atd_radius_live_sessions s
            JOIN users u ON u.user_id=s.user_id
            LEFT JOIN normal_users nu ON nu.user_id=s.user_id
            LEFT JOIN voip_users vu ON vu.user_id=s.user_id
            WHERE s.state->>'started'='true' AND s.state->>'stopped'='false'
            ORDER BY s.user_id, s.ras_id, s.unique_id
            """
        ).fetchall()
        reservations = conn.execute(
            """
            SELECT r.user_id, r.ras_id, r.username, r.created_at,
                   r.ras_multi_login_allowed, u.owner_id,
                   COALESCE(nu.normal_username, vu.voip_username)
            FROM atd_radius_login_reservations r
            JOIN users u ON u.user_id=r.user_id
            LEFT JOIN normal_users nu ON nu.user_id=r.user_id
            LEFT JOIN voip_users vu ON vu.user_id=r.user_id
            ORDER BY r.user_id, r.created_at, r.reservation_id
            """
        ).fetchall()

    sessions: list[OnlineSessionView] = []
    for row in rows:
        if not can_see_online_users(admin, int(row[4]) if row[4] is not None else None):
            continue
        payload = _json_object(row[3])
        attrs = _json_object(payload.get("attributes", {}))
        sessions.append(
            OnlineSessionView(
                user_id=int(row[0]),
                username=str(row[5]) if row[5] is not None else None,
                ras_id=int(row[1]),
                unique_id=str(row[2]),
                started_at=_iso(payload.get("started_at")),
                service=str(payload.get("charge_kind") or "unknown"),
                remote_ip=str(attrs.get("Framed-IP-Address") or attrs.get("remote_ip") or "") or None,
                nas_port=str(attrs.get("NAS-Port") or attrs.get("NAS-Port-Id") or "") or None,
                input_octets=max(0, int(payload.get("input_octets", 0))),
                output_octets=max(0, int(payload.get("output_octets", 0))),
                termination_requested=bool(payload.get("termination_requested_reason")),
            )
        )

    login_in_progress = [
        LoginInProgressView(
            user_id=int(row[0]),
            username=str(row[2]),
            ras_id=int(row[1]),
            created_at=_iso(row[3]) or "",
            ras_multi_login_allowed=bool(row[4]) if row[4] is not None else None,
        )
        for row in reservations
        if can_see_online_users(admin, int(row[5]) if row[5] is not None else None)
    ]
    return OnlineSessionsView(sessions=sessions, login_in_progress=login_in_progress)


@router.post("/disconnect", response_model=KillOnlineSessionView, status_code=202)
def kill_online_session(
    payload: KillOnlineSessionPayload,
    request: Request,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> KillOnlineSessionView:
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    handler = getattr(request.app.state, "radius_packet_handler", None)
    if handler is None:
        raise HTTPException(status_code=503, detail="RADIUS runtime is not initialized")

    key = SessionKey(payload.user_id, payload.ras_id, payload.unique_id)
    with connection() as conn:
        row = conn.execute(
            "SELECT owner_id FROM users WHERE user_id=%s",
            (payload.user_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="user not found")
        owner_id = int(row[0]) if row[0] is not None else None
        if not can_kill_user(admin, owner_id):
            raise HTTPException(status_code=403, detail="KILL USER permission denied")

        # Reconcile this user's full durable state before accepting a target.
        handler._refresh_durable_user_sessions(conn, payload.user_id)
        session = handler.state.sessions.get(key)
        if session is None or session.stopped:
            raise HTTPException(status_code=404, detail="online session not found")

    reason = f"killed_by_admin:{admin.username}"
    try:
        handler._terminate_voip_session(key, reason)
    except Exception as exc:
        try:
            with connection() as audit_conn:
                OperationalAuditRepository(audit_conn).append(
                    actor_admin_id=admin.admin_id,
                    actor_username=admin.username,
                    action="user.session.termination",
                    outcome="failed",
                    target_type="radius_session",
                    target_id=f"{payload.user_id}:{payload.ras_id}:{payload.unique_id}",
                    remote_addr=remote_addr,
                    details={"reason": reason, "error_type": type(exc).__name__},
                )
                audit_conn.commit()
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="RAS termination request failed") from exc

    with connection() as audit_conn:
        OperationalAuditRepository(audit_conn).append(
            actor_admin_id=admin.admin_id,
            actor_username=admin.username,
            action="user.session.termination",
            outcome="success",
            target_type="radius_session",
            target_id=f"{payload.user_id}:{payload.ras_id}:{payload.unique_id}",
            remote_addr=remote_addr,
            details={"reason": reason, "remote_disappearance_verified": False},
        )
        audit_conn.commit()

    return KillOnlineSessionView(
        user_id=payload.user_id,
        ras_id=payload.ras_id,
        unique_id=payload.unique_id,
        termination_requested=True,
        note="Provider termination was requested; final session removal is confirmed by Accounting-Stop.",
    )


@router.post("/clear", response_model=ClearOnlineSessionView)
def clear_online_session(
    payload: KillOnlineSessionPayload,
    request: Request,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> ClearOnlineSessionView:
    """Mirror A1.24 CLEAR USER: local logout only, without credit deduction or RAS kill."""
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    handler = getattr(request.app.state, "radius_packet_handler", None)
    clear_method = getattr(handler, "clear_user_session", None)
    if not callable(clear_method):
        raise HTTPException(status_code=503, detail="RADIUS runtime does not support CLEAR USER")

    key = SessionKey(payload.user_id, payload.ras_id, payload.unique_id)
    with connection() as conn:
        row = conn.execute("SELECT owner_id FROM users WHERE user_id=%s", (payload.user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="user not found")
        owner_id = int(row[0]) if row[0] is not None else None
        if not can_clear_user(admin, owner_id):
            raise HTTPException(status_code=403, detail="CLEAR USER permission denied")

    try:
        clear_method(key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="online session not found") from exc
    except Exception as exc:
        try:
            with connection() as audit_conn:
                OperationalAuditRepository(audit_conn).append(
                    actor_admin_id=admin.admin_id,
                    actor_username=admin.username,
                    action="user.session.clear",
                    outcome="failed",
                    target_type="radius_session",
                    target_id=f"{payload.user_id}:{payload.ras_id}:{payload.unique_id}",
                    remote_addr=remote_addr,
                    details={"credit_deducted": False, "ras_disconnect_sent": False, "error_type": type(exc).__name__},
                )
                audit_conn.commit()
        except Exception:
            pass
        raise HTTPException(status_code=409, detail="Local session clear failed") from exc

    with connection() as audit_conn:
        OperationalAuditRepository(audit_conn).append(
            actor_admin_id=admin.admin_id,
            actor_username=admin.username,
            action="user.session.clear",
            outcome="success",
            target_type="radius_session",
            target_id=f"{payload.user_id}:{payload.ras_id}:{payload.unique_id}",
            remote_addr=remote_addr,
            details={"credit_deducted": False, "ras_disconnect_sent": False},
        )
        audit_conn.commit()

    return ClearOnlineSessionView(
        user_id=payload.user_id,
        ras_id=payload.ras_id,
        unique_id=payload.unique_id,
        cleared_locally=True,
        credit_deducted=False,
        ras_disconnect_sent=False,
        note="Local IBSng session state was cleared; no RAS disconnect command was sent and no user credit was deducted.",
    )
