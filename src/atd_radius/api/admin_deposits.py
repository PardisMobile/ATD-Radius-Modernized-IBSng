from __future__ import annotations

import ipaddress
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.admin_deposit_repository import AdminDepositRepository
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository

router = APIRouter(prefix="/admins", tags=["ADMIN"])


class AdminDepositChange(BaseModel):
    delta: Decimal = Field(max_digits=12, decimal_places=2)
    comment: str = Field(max_length=1000)


class AdminDepositView(BaseModel):
    admin_id: int
    username: str
    deposit: Decimal


@router.post("/{username}/deposit", response_model=AdminDepositView)
def change_admin_deposit(
    username: str,
    payload: AdminDepositChange,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE ADMIN DEPOSIT")),
) -> AdminDepositView:
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    try:
        with connection() as conn:
            repository = AdminDepositRepository(conn)
            target = repository.lock_target(username)
            if target is None:
                raise HTTPException(status_code=404, detail="administrator not found")
            resulting_deposit = repository.change(
                target,
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                delta=payload.delta,
                remote_addr=remote_addr,
                comment=payload.comment,
            )
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="admin.deposit.change",
                outcome="success",
                target_type="admin",
                target_id=str(target.admin_id),
                remote_addr=remote_addr,
                details={
                    "target_username": target.username,
                    "delta": str(payload.delta),
                    "resulting_deposit": str(resulting_deposit),
                    "comment": payload.comment,
                },
            )
            conn.commit()
            return AdminDepositView(
                admin_id=target.admin_id,
                username=target.username,
                deposit=resulting_deposit,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Administrator deposit could not be changed") from exc
