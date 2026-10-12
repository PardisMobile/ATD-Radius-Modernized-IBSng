"""Source-backed REST access to the IBSng A1.24 IAS event queue."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.ias_events_repository import PostgresIASEventRepository
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository

router = APIRouter(prefix="/ias/events", tags=["IAS EVENTS"])


class IASEventView(BaseModel):
    event_id: int
    event_type: int
    event_type_name: str
    event_date: datetime
    actor: str
    amount: Decimal | None
    destinations: str
    comment: str


class DeleteIASEventsPayload(BaseModel):
    event_ids: list[int] = Field(default_factory=list)


def _view(event) -> IASEventView:
    return IASEventView(
        event_id=event.event_id,
        event_type=event.event_type,
        event_type_name=event.event_type_name,
        event_date=event.event_date,
        actor=event.actor,
        amount=event.amount,
        destinations=event.destinations,
        comment=event.comment,
    )


@router.get("", response_model=list[IASEventView])
def list_ias_events(
    from_event_id: int = Query(...),
    from_offset: int = Query(0, alias="from", ge=0),
    to_offset: int = Query(100, alias="to", ge=0, le=50 * 1024 * 1024),
    admin: AdminPrincipal = Depends(require_admin_permission("HANDLE IAS EVENTS")),
) -> list[IASEventView]:
    try:
        with connection() as conn:
            events = PostgresIASEventRepository(conn).list_events(
                from_event_id, from_offset, to_offset
            )
        return [_view(event) for event in events]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("", status_code=204)
def delete_ias_events(
    payload: DeleteIASEventsPayload = Body(...),
    admin: AdminPrincipal = Depends(require_admin_permission("HANDLE IAS EVENTS")),
) -> None:
    with connection() as conn:
        repo = PostgresIASEventRepository(conn)
        deleted = repo.delete_events(payload.event_ids)
        OperationalAuditRepository(conn).append(
            actor_admin_id=admin.admin_id,
            actor_username=admin.username,
            action="ias.events.delete",
            outcome="success",
            target_type="ias_event",
            target_id=",".join(str(event_id) for event_id in payload.event_ids),
            remote_addr=admin.remote_addr,
            details={"requested_count": len(payload.event_ids), "deleted_count": deleted},
        )
        conn.commit()
