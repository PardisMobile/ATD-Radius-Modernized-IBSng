"""Source-backed API for the IBSng A1.24 VoIP tariff catalog."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository
from atd_radius.infrastructure.voip_tariff_repository import (
    PostgresVoipTariffRepository,
    PrefixConflictError,
    PrefixInput,
    PrefixInputError,
    PrefixNotFound,
    TariffAlreadyExists,
    TariffInUseError,
    TariffNotFound,
)

router = APIRouter(prefix="/voip-tariffs", tags=["VOIP TARIFF"])


class PrefixView(BaseModel):
    prefix_id: int
    prefix_code: str
    prefix_name: str
    cpm: str
    free_seconds: int
    min_duration: int
    round_to: int
    min_chargable_duration: int


class VoipTariffView(BaseModel):
    tariff_id: int
    tariff_name: str
    comment: str
    prefixes: list[PrefixView] = Field(default_factory=list)


class TariffPayload(BaseModel):
    tariff_name: str = Field(min_length=1, max_length=255)
    comment: str = ""

    @field_validator("tariff_name")
    @classmethod
    def source_valid_name(cls, value: str) -> str:
        # A1.24 isValidName allows only ASCII alphanumeric, underscore and hyphen.
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("invalid A1.24 tariff name")
        return value


class PrefixPayload(BaseModel):
    prefix_code: str
    prefix_name: str
    cpm: Decimal = Field(ge=0)
    free_seconds: int = Field(ge=0)
    min_duration: int = Field(ge=0)
    round_to: int = Field(ge=0)
    min_chargable_duration: int = Field(ge=0)

    @field_validator("prefix_code")
    @classmethod
    def source_valid_prefix_code(cls, value: str) -> str:
        if not value or not value.isdigit():
            raise ValueError("prefix code must contain digits only")
        return value

    def to_domain(self) -> PrefixInput:
        return PrefixInput(
            code=self.prefix_code,
            name=self.prefix_name,
            cpm=self.cpm,
            free_seconds=self.free_seconds,
            min_duration=self.min_duration,
            round_to=self.round_to,
            min_chargeable_duration=self.min_chargable_duration,
        )


def _view(tariff, *, include_prefixes: bool, name_regex: str) -> VoipTariffView:
    prefixes = []
    if include_prefixes:
        try:
            pattern = re.compile(name_regex) if name_regex else None
        except re.error as exc:
            raise HTTPException(status_code=422, detail="Invalid prefix name regular expression") from exc
        for prefix in tariff.prefixes:
            if pattern is None or pattern.match(prefix.name):
                prefixes.append(
                    PrefixView(
                        prefix_id=prefix.prefix_id,
                        prefix_code=prefix.code,
                        prefix_name=prefix.name,
                        cpm=str(prefix.cpm),
                        free_seconds=prefix.free_seconds,
                        min_duration=prefix.min_duration,
                        round_to=prefix.round_to,
                        min_chargable_duration=prefix.min_chargeable_duration,
                    )
                )
    return VoipTariffView(
        tariff_id=tariff.tariff_id,
        tariff_name=tariff.name,
        comment=tariff.comment,
        prefixes=prefixes,
    )


def _audit(conn, admin: AdminPrincipal, action: str, target_id: str, details: dict) -> None:
    OperationalAuditRepository(conn).append(
        actor_admin_id=admin.admin_id,
        actor_username=admin.username,
        action=action,
        outcome="success",
        target_type="voip_tariff",
        target_id=target_id,
        remote_addr=admin.remote_addr,
        details=details,
    )


def _mutation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TariffNotFound | PrefixNotFound):
        return HTTPException(status_code=404, detail="VoIP tariff or prefix not found")
    if isinstance(exc, TariffAlreadyExists | PrefixConflictError):
        return HTTPException(status_code=409, detail="VoIP tariff or prefix already exists")
    if isinstance(exc, TariffInUseError):
        return HTTPException(status_code=409, detail="VoIP tariff is referenced by a charge rule")
    if isinstance(exc, PrefixInputError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=409, detail="VoIP tariff could not be changed")


@router.get("", response_model=list[VoipTariffView])
def list_voip_tariffs(
    admin: AdminPrincipal = Depends(require_admin_permission("SEE VOIP TARIFF")),
) -> list[VoipTariffView]:
    """List tariffs without prefixes, matching the native listTariffs workflow."""
    with connection() as conn:
        tariffs = PostgresVoipTariffRepository(conn).list()
    return [_view(tariff, include_prefixes=False, name_regex="") for tariff in sorted(tariffs, key=lambda item: item.name)]


@router.get("/{tariff_name}", response_model=VoipTariffView)
def get_voip_tariff(
    tariff_name: str,
    include_prefixes: bool = Query(default=False),
    name_regex: str = Query(default=""),
    admin: AdminPrincipal = Depends(require_admin_permission("SEE VOIP TARIFF")),
) -> VoipTariffView:
    with connection() as conn:
        tariff = PostgresVoipTariffRepository(conn).get_by_name(tariff_name)
    if tariff is None:
        raise HTTPException(status_code=404, detail="VoIP tariff not found")
    return _view(tariff, include_prefixes=include_prefixes, name_regex=name_regex)


@router.post("", response_model=VoipTariffView, status_code=201)
def create_voip_tariff(
    payload: TariffPayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE VOIP TARIFF")),
) -> VoipTariffView:
    try:
        with connection() as conn:
            repo = PostgresVoipTariffRepository(conn)
            tariff_id = repo.create_tariff(payload.tariff_name, payload.comment)
            _audit(conn, admin, "voip_tariff.create", str(tariff_id), {"tariff_name": payload.tariff_name})
            conn.commit()
            tariff = repo.get(tariff_id)
            if tariff is None:
                raise RuntimeError("created tariff could not be reloaded")
            return _view(tariff, include_prefixes=True, name_regex="")
    except (TariffAlreadyExists,) as exc:
        raise _mutation_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise _mutation_error(exc) from exc


@router.put("/{tariff_id}", response_model=VoipTariffView)
def update_voip_tariff(
    tariff_id: int,
    payload: TariffPayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE VOIP TARIFF")),
) -> VoipTariffView:
    try:
        with connection() as conn:
            repo = PostgresVoipTariffRepository(conn)
            repo.update_tariff(tariff_id, payload.tariff_name, payload.comment)
            _audit(conn, admin, "voip_tariff.update", str(tariff_id), {"tariff_name": payload.tariff_name})
            tariff = repo.get(tariff_id)
            if tariff is None:
                raise RuntimeError("updated tariff could not be reloaded")
            conn.commit()
            return _view(tariff, include_prefixes=True, name_regex="")
    except Exception as exc:
        raise _mutation_error(exc) from exc


@router.delete("/{tariff_name}", status_code=204)
def delete_voip_tariff(
    tariff_name: str,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE VOIP TARIFF")),
) -> None:
    try:
        with connection() as conn:
            repo = PostgresVoipTariffRepository(conn)
            tariff_id = repo.delete_tariff(tariff_name)
            _audit(conn, admin, "voip_tariff.delete", str(tariff_id), {"tariff_name": tariff_name})
            conn.commit()
    except Exception as exc:
        raise _mutation_error(exc) from exc


@router.post("/{tariff_name}/prefixes", response_model=list[PrefixView], status_code=201)
def add_voip_prefixes(
    tariff_name: str,
    prefixes: list[PrefixPayload],
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE VOIP TARIFF")),
) -> list[PrefixView]:
    try:
        with connection() as conn:
            repo = PostgresVoipTariffRepository(conn)
            prefix_ids = repo.add_prefixes(tariff_name, [item.to_domain() for item in prefixes])
            _audit(conn, admin, "voip_tariff.prefixes.add", tariff_name, {"prefix_ids": prefix_ids})
            tariff = repo.get_by_name(tariff_name)
            conn.commit()
            if tariff is None:
                raise RuntimeError("tariff could not be reloaded")
            selected = {item.prefix_id for item in tariff.prefixes if item.prefix_id in prefix_ids}
            return [_view(tariff, include_prefixes=True, name_regex="").prefixes[i]
                    for i, item in enumerate(tariff.prefixes) if item.prefix_id in selected]
    except Exception as exc:
        raise _mutation_error(exc) from exc


@router.put("/{tariff_name}/prefixes/{prefix_id}", response_model=PrefixView)
def update_voip_prefix(
    tariff_name: str,
    prefix_id: int,
    payload: PrefixPayload,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE VOIP TARIFF")),
) -> PrefixView:
    try:
        with connection() as conn:
            repo = PostgresVoipTariffRepository(conn)
            repo.update_prefix(tariff_name, prefix_id, payload.to_domain())
            _audit(conn, admin, "voip_tariff.prefix.update", tariff_name, {"prefix_id": prefix_id})
            tariff = repo.get_by_name(tariff_name)
            if tariff is None:
                raise RuntimeError("tariff could not be reloaded")
            prefix = next((item for item in tariff.prefixes if item.prefix_id == prefix_id), None)
            if prefix is None:
                raise RuntimeError("updated prefix could not be reloaded")
            conn.commit()
            return _view(tariff, include_prefixes=True, name_regex="").prefixes[
                next(i for i, item in enumerate(tariff.prefixes) if item.prefix_id == prefix_id)
            ]
    except Exception as exc:
        raise _mutation_error(exc) from exc


@router.delete("/{tariff_name}/prefixes", status_code=204)
def delete_voip_prefixes(
    tariff_name: str,
    prefix_code: list[str] = Query(min_length=1),
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE VOIP TARIFF")),
) -> None:
    try:
        with connection() as conn:
            repo = PostgresVoipTariffRepository(conn)
            count = repo.delete_prefixes(tariff_name, prefix_code)
            _audit(conn, admin, "voip_tariff.prefixes.delete", tariff_name, {"prefix_codes": prefix_code, "count": count})
            conn.commit()
    except Exception as exc:
        raise _mutation_error(exc) from exc
