"""Source-backed API for native IBSng A1.24 Internet charge rules."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.billing_rules import (
    InternetChargeNotFound,
    InternetChargeRuleInput,
    InternetChargeTypeError,
    InternetRuleConflictError,
    InternetRuleInputError,
    InternetRuleNotFound,
    PostgresInternetChargeRuleRepository,
)
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository

router = APIRouter(prefix="/internet-charge-rules", tags=["INTERNET CHARGE RULES"])
_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class InternetChargeRulePayload(BaseModel):
    charge_name: str = Field(min_length=1)
    start_time: str
    end_time: str
    day_of_weeks: list[str] = Field(min_length=1)
    cpm: Decimal = Field(ge=0)
    cpk: Decimal = Field(ge=0)
    assumed_kps: int = Field(gt=0)
    bandwidth_limit_kbytes: int = Field(ge=0)
    tx_leaf_name: str = ""
    rx_leaf_name: str = ""
    ras_id: int | None = None
    ports: list[str] = Field(default_factory=list)


class InternetChargeRuleView(BaseModel):
    rule_id: int
    charge_id: int
    charge_name: str
    start_time: str
    end_time: str
    day_of_weeks: list[str]
    ras_id: int | None
    ports: list[str | None]
    cpm: Decimal
    cpk: Decimal
    assumed_kps: int
    bandwidth_limit_kbytes: int
    bw_tx_leaf_name: str
    bw_rx_leaf_name: str


def _input(payload: InternetChargeRulePayload) -> InternetChargeRuleInput:
    return InternetChargeRuleInput(
        start_time=payload.start_time,
        end_time=payload.end_time,
        days=tuple(payload.day_of_weeks),
        cpm=payload.cpm,
        cpk=payload.cpk,
        assumed_kps=payload.assumed_kps,
        bandwidth_limit_kbytes=payload.bandwidth_limit_kbytes,
        tx_leaf_name=payload.tx_leaf_name,
        rx_leaf_name=payload.rx_leaf_name,
        ras_id=payload.ras_id,
        ports=tuple(payload.ports),
    )


def _view(conn, rule) -> InternetChargeRuleView:
    charge_rows = conn.execute("SELECT name FROM charges WHERE charge_id=%s", (rule.charge_id,)).fetchall()
    charge_name = str(charge_rows[0][0]) if charge_rows else ""
    def leaf_name(leaf_id: int | None) -> str:
        if leaf_id is None:
            return ""
        rows = conn.execute("SELECT leaf_name FROM bw_leaf WHERE leaf_id=%s", (leaf_id,)).fetchall()
        return str(rows[0][0]) if rows else ""
    return InternetChargeRuleView(
        rule_id=rule.rule_id,
        charge_id=rule.charge_id,
        charge_name=charge_name,
        start_time=f"{rule.start_second // 3600:02d}:{(rule.start_second % 3600) // 60:02d}:{rule.start_second % 60:02d}",
        end_time=f"{rule.end_second // 3600:02d}:{(rule.end_second % 3600) // 60:02d}:{rule.end_second % 60:02d}",
        day_of_weeks=[_DAYS[day] for day in sorted(rule.days)],
        ras_id=rule.ras_id,
        ports=sorted(rule.ports, key=lambda port: "" if port is None else port),
        cpm=rule.cpm,
        cpk=rule.cpk,
        assumed_kps=rule.assumed_kps,
        bandwidth_limit_kbytes=rule.bandwidth_limit_kbytes,
        bw_tx_leaf_name=leaf_name(rule.bw_transmit_leaf_id),
        bw_rx_leaf_name=leaf_name(rule.bw_receive_leaf_id),
    )


def _audit(conn, admin: AdminPrincipal, action: str, rule_id: int, details: dict) -> None:
    OperationalAuditRepository(conn).append(
        actor_admin_id=admin.admin_id,
        actor_username=admin.username,
        action=action,
        outcome="success",
        target_type="internet_charge_rule",
        target_id=str(rule_id),
        remote_addr=admin.remote_addr,
        details=details,
    )


def _mutation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (InternetChargeNotFound, InternetRuleNotFound)):
        return HTTPException(status_code=404, detail="Internet charge or rule not found")
    if isinstance(exc, InternetChargeTypeError):
        return HTTPException(status_code=422, detail="Charge is not an Internet charge")
    if isinstance(exc, InternetRuleConflictError):
        return HTTPException(status_code=409, detail="Internet charge rule overlaps an existing rule")
    if isinstance(exc, InternetRuleInputError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=409, detail="Internet charge rule could not be changed")


@router.get("", response_model=list[InternetChargeRuleView])
def list_internet_charge_rules(
    charge_id: int | None = None,
    admin: AdminPrincipal = Depends(require_admin_permission("ACCESS ALL CHARGES")),
) -> list[InternetChargeRuleView]:
    with connection() as conn:
        repo = PostgresInternetChargeRuleRepository(conn)
        return [_view(conn, rule) for rule in repo.list(charge_id)]


@router.post("", response_model=InternetChargeRuleView, status_code=201)
def create_internet_charge_rule(
    payload: InternetChargeRulePayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> InternetChargeRuleView:
    try:
        with connection() as conn:
            repo = PostgresInternetChargeRuleRepository(conn)
            rule_id = repo.create(payload.charge_name, _input(payload))
            _audit(conn, admin, "internet_charge_rule.create", rule_id, {"charge_name": payload.charge_name})
            rule = repo.get(rule_id)
            if rule is None:
                raise RuntimeError("created Internet rule could not be reloaded")
            result = _view(conn, rule)
            conn.commit()
            return result
    except Exception as exc:
        raise _mutation_error(exc) from exc


@router.put("/{rule_id}", response_model=InternetChargeRuleView)
def update_internet_charge_rule(
    rule_id: int,
    payload: InternetChargeRulePayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> InternetChargeRuleView:
    try:
        with connection() as conn:
            repo = PostgresInternetChargeRuleRepository(conn)
            repo.update(payload.charge_name, rule_id, _input(payload))
            _audit(conn, admin, "internet_charge_rule.update", rule_id, {"charge_name": payload.charge_name})
            rule = repo.get(rule_id)
            if rule is None:
                raise RuntimeError("updated Internet rule could not be reloaded")
            result = _view(conn, rule)
            conn.commit()
            return result
    except Exception as exc:
        raise _mutation_error(exc) from exc


@router.delete("/{charge_name}/{rule_id}", status_code=204)
def delete_internet_charge_rule(
    charge_name: str,
    rule_id: int,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE CHARGE")),
) -> None:
    try:
        with connection() as conn:
            PostgresInternetChargeRuleRepository(conn).delete(charge_name, rule_id)
            _audit(conn, admin, "internet_charge_rule.delete", rule_id, {"charge_name": charge_name})
            conn.commit()
    except Exception as exc:
        raise _mutation_error(exc) from exc
