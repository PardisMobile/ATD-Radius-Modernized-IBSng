"""Source-backed administration endpoints for native VoIP charge rules."""
from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository
from atd_radius.infrastructure.voip_charge_rules import (
    ChargeNotFound,
    ChargeTypeError,
    PostgresVoipChargeRuleRepository,
    VoipChargeRuleInput,
    VoipRuleConflictError,
    VoipRuleInputError,
    VoipRuleNotFound,
    VoipTariffNotFound,
)

router = APIRouter(prefix="/voip-charge-rules", tags=["VOIP CHARGE RULES"])


class VoipChargeRulePayload(BaseModel):
    charge_name: str = Field(min_length=1)
    start_time: str
    end_time: str
    days: list[str] = Field(min_length=1)
    tariff_name: str = Field(min_length=1)
    ras_id: int | None = None
    ports: list[str] = Field(default_factory=list)


class VoipChargeRuleView(BaseModel):
    rule_id: int
    charge_id: int
    tariff_id: int
    tariff_name: str
    start_time: str
    end_time: str
    days: list[str]
    ras_id: int | None
    ports: list[str]
    time_limit: int | None


_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _payload(payload: VoipChargeRulePayload) -> VoipChargeRuleInput:
    return VoipChargeRuleInput(
        start_time=payload.start_time,
        end_time=payload.end_time,
        days=tuple(payload.days),
        tariff_name=payload.tariff_name,
        ras_id=payload.ras_id,
        ports=tuple(payload.ports),
    )


def _view(rule, tariff_name: str) -> VoipChargeRuleView:
    return VoipChargeRuleView(
        rule_id=rule.rule_id,
        charge_id=rule.charge_id,
        tariff_id=rule.tariff_id,
        tariff_name=tariff_name,
        start_time=f"{rule.start_second // 3600:02d}:{(rule.start_second % 3600) // 60:02d}:{rule.start_second % 60:02d}",
        end_time=f"{rule.end_second // 3600:02d}:{(rule.end_second % 3600) // 60:02d}:{rule.end_second % 60:02d}",
        days=[_DAY_NAMES[day] for day in sorted(rule.days)],
        ras_id=rule.ras_id,
        ports=sorted(rule.ports),
        time_limit=rule.time_limit,
    )


def _audit(conn, admin: AdminPrincipal, action: str, rule_id: int, details: dict) -> None:
    OperationalAuditRepository(conn).append(
        actor_admin_id=admin.admin_id,
        actor_username=admin.username,
        action=action,
        outcome="success",
        target_type="voip_charge_rule",
        target_id=str(rule_id),
        remote_addr=admin.remote_addr,
        details=details,
    )


def _raise_mutation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ChargeNotFound, VoipTariffNotFound, VoipRuleNotFound)):
        return HTTPException(status_code=404, detail="VoIP charge, tariff, or rule not found")
    if isinstance(exc, ChargeTypeError):
        return HTTPException(status_code=422, detail="Charge is not a VoIP charge")
    if isinstance(exc, VoipRuleConflictError):
        return HTTPException(status_code=409, detail="VoIP charge rule overlaps an existing rule")
    if isinstance(exc, VoipRuleInputError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=409, detail="VoIP charge rule could not be changed")


@router.get("", response_model=list[VoipChargeRuleView])
def list_voip_charge_rules(
    charge_id: int | None = None,
    admin: AdminPrincipal = Depends(require_admin_permission("ACCESS ALL CHARGES")),
) -> list[VoipChargeRuleView]:
    with connection() as conn:
        repo = PostgresVoipChargeRuleRepository(conn)
        rules = repo.list(charge_id)
        tariffs = {
            int(row[0]): str(row[1])
            for row in conn.execute(
                "SELECT tariff_id, tariff_name FROM voip_charge_rule_tariff"
            ).fetchall()
        }
        return [_view(rule, tariffs.get(rule.tariff_id, "")) for rule in rules]


@router.post("", response_model=VoipChargeRuleView, status_code=201)
def create_voip_charge_rule(
    payload: VoipChargeRulePayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> VoipChargeRuleView:
    try:
        with connection() as conn:
            repo = PostgresVoipChargeRuleRepository(conn)
            rule_id = repo.create(payload.charge_name, _payload(payload))
            _audit(conn, admin, "voip_charge_rule.create", rule_id, {"charge_name": payload.charge_name, "tariff_name": payload.tariff_name})
            rule = repo.get(rule_id)
            if rule is None:
                raise RuntimeError("created VoIP rule could not be reloaded")
            tariff_name = payload.tariff_name
            conn.commit()
            return _view(rule, tariff_name)
    except Exception as exc:
        raise _raise_mutation_error(exc) from exc


@router.put("/{rule_id}", response_model=VoipChargeRuleView)
def update_voip_charge_rule(
    rule_id: int,
    payload: VoipChargeRulePayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> VoipChargeRuleView:
    try:
        with connection() as conn:
            repo = PostgresVoipChargeRuleRepository(conn)
            repo.update(payload.charge_name, rule_id, _payload(payload))
            _audit(conn, admin, "voip_charge_rule.update", rule_id, {"charge_name": payload.charge_name, "tariff_name": payload.tariff_name})
            rule = repo.get(rule_id)
            if rule is None:
                raise RuntimeError("updated VoIP rule could not be reloaded")
            conn.commit()
            return _view(rule, payload.tariff_name)
    except Exception as exc:
        raise _raise_mutation_error(exc) from exc


@router.delete("/{charge_name}/{rule_id}", status_code=204)
def delete_voip_charge_rule(
    charge_name: str,
    rule_id: int,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> None:
    try:
        with connection() as conn:
            repo = PostgresVoipChargeRuleRepository(conn)
            repo.delete(charge_name, rule_id)
            _audit(conn, admin, "voip_charge_rule.delete", rule_id, {"charge_name": charge_name})
            conn.commit()
    except Exception as exc:
        raise _raise_mutation_error(exc) from exc
