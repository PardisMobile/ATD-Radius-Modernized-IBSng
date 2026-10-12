"""IAS user-info projection for integrations replacing the native IAS handler."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.ias_user_info import PostgresIASUserInfoRepository

router = APIRouter(prefix="/ias/users", tags=["IAS EVENTS"])


class IASUserInfoView(BaseModel):
    user_id: int
    owner: str
    credit: Decimal
    normal_username: str | None
    voip_username: str | None


@router.get("", response_model=list[IASUserInfoView])
def get_ias_user_info(
    user_ids: list[int] = Query(...),
    admin: AdminPrincipal = Depends(require_admin_permission("GOD")),
) -> list[IASUserInfoView]:
    try:
        with connection() as conn:
            users = PostgresIASUserInfoRepository(conn).get_many(user_ids)
        return [
            IASUserInfoView(
                user_id=user.user_id,
                owner=user.owner,
                credit=user.credit,
                normal_username=user.normal_username,
                voip_username=user.voip_username,
            )
            for user in users
        ]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
