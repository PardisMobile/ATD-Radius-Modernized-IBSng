"""Source-backed administration API for IBSng A1.24 charges."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
import re

from pydantic import BaseModel, Field, field_validator

from atd_radius.api.admin_dependencies import AdminPrincipal, can_use_charge, require_admin_permission, require_admin_session
from atd_radius.infrastructure.charges import (
    ChargeAlreadyExists,
    ChargeInUseError,
    ChargeInputError,
    ChargeNotFound,
    PostgresChargeRepository,
)
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository

router = APIRouter(prefix="/charges", tags=["CHARGES"])


class ChargeCreatePayload(BaseModel):
    charge_name: str = Field(min_length=1)
    comment: str = ""
    charge_type: str
    visible_to_all: bool = False

    @field_validator("charge_name")
    @classmethod
    def source_valid_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("invalid A1.24 charge name")
        return value

    @field_validator("charge_type")
    @classmethod
    def source_valid_type(cls, value: str) -> str:
        if value not in {"Internet", "VoIP"}:
            raise ValueError("charge_type must be Internet or VoIP")
        return value


class ChargeUpdatePayload(BaseModel):
    charge_name: str = Field(min_length=1)
    comment: str = ""
    visible_to_all: bool = False

    @field_validator("charge_name")
    @classmethod
    def source_valid_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("invalid A1.24 charge name")
        return value


class ChargeView(BaseModel):
    charge_id: int
    charge_name: str
    comment: str
    charge_type: str
    admin_id: int | None
    visible_to_all: bool


def accessible_charge_ids(charges, admin: AdminPrincipal, charge_id: int | None) -> list[int]:
    """Resolve charge visibility using A1.24 Admin.canUseCharge semantics."""
    if charge_id is not None:
        selected = next((charge for charge in charges if charge.charge_id == charge_id), None)
        if selected is None:
            raise HTTPException(status_code=404, detail="Charge not found")
        if not can_use_charge(admin, selected.name, selected.visible_to_all):
            raise HTTPException(status_code=403, detail="Administrator cannot use this charge")
        return [selected.charge_id]
    return [
        charge.charge_id for charge in charges
        if can_use_charge(admin, charge.name, charge.visible_to_all)
    ]


def _view(charge) -> ChargeView:
    return ChargeView(
        charge_id=charge.charge_id, charge_name=charge.name, comment=charge.comment,
        charge_type=charge.charge_type, admin_id=charge.admin_id,
        visible_to_all=charge.visible_to_all,
    )


def _audit(conn, admin: AdminPrincipal, action: str, charge_id: int, details: dict) -> None:
    OperationalAuditRepository(conn).append(
        actor_admin_id=admin.admin_id,
        actor_username=admin.username,
        action=action,
        outcome="success",
        target_type="charge",
        target_id=str(charge_id),
        remote_addr=admin.remote_addr,
        details=details,
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, ChargeNotFound):
        return HTTPException(status_code=404, detail="Charge not found")
    if isinstance(exc, (ChargeAlreadyExists, ChargeInUseError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ChargeInputError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=409, detail="Charge could not be changed")


@router.get("", response_model=list[ChargeView])
def list_charges(
    admin: AdminPrincipal = Depends(require_admin_session),
) -> list[ChargeView]:
    with connection() as conn:
        charges = PostgresChargeRepository(conn).list()
        return [_view(charge) for charge in charges if can_use_charge(admin, charge.name, charge.visible_to_all)]


@router.get("/{charge_name}", response_model=ChargeView)
def get_charge(
    charge_name: str,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> ChargeView:
    with connection() as conn:
        charge = PostgresChargeRepository(conn).get_by_name(charge_name)
    if charge is None:
        raise HTTPException(status_code=404, detail="Charge not found")
    if not can_use_charge(admin, charge.name, charge.visible_to_all):
        raise HTTPException(status_code=403, detail="Administrator cannot use this charge")
    return _view(charge)


@router.post("", response_model=ChargeView, status_code=201)
def create_charge(
    payload: ChargeCreatePayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> ChargeView:
    try:
        with connection() as conn:
            repo = PostgresChargeRepository(conn)
            charge_id = repo.create(
                payload.charge_name, payload.comment, payload.charge_type,
                admin.admin_id, payload.visible_to_all,
            )
            _audit(conn, admin, "charge.create", charge_id, {
                "charge_name": payload.charge_name, "charge_type": payload.charge_type,
            })
            charge = repo.get(charge_id)
            if charge is None:
                raise RuntimeError("created charge could not be reloaded")
            result = _view(charge)
            conn.commit()
            return result
    except Exception as exc:
        raise _error(exc) from exc


@router.put("/{charge_id}", response_model=ChargeView)
def update_charge(
    charge_id: int,
    payload: ChargeUpdatePayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> ChargeView:
    try:
        with connection() as conn:
            repo = PostgresChargeRepository(conn)
            repo.update(charge_id, payload.charge_name, payload.comment, payload.visible_to_all)
            _audit(conn, admin, "charge.update", charge_id, {"charge_name": payload.charge_name})
            charge = repo.get(charge_id)
            if charge is None:
                raise RuntimeError("updated charge could not be reloaded")
            result = _view(charge)
            conn.commit()
            return result
    except Exception as exc:
        raise _error(exc) from exc


@router.delete("/{charge_name}", status_code=204)
def delete_charge(
    charge_name: str,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> None:
    try:
        with connection() as conn:
            repo = PostgresChargeRepository(conn)
            charge_id = repo.delete(charge_name)
            _audit(conn, admin, "charge.delete", charge_id, {"charge_name": charge_name})
            conn.commit()
    except Exception as exc:
        raise _error(exc) from exc
