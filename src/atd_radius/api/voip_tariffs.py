"""Read-only API for the source-defined IBSng VoIP tariff catalog."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.voip_tariff_repository import PostgresVoipTariffRepository

router = APIRouter(prefix="/voip-tariffs", tags=["VOIP TARIFF"])


class VoipPrefixView(BaseModel):
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
    prefixes: list[VoipPrefixView] = []


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
                    VoipPrefixView(
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


@router.get("", response_model=list[VoipTariffView])
def list_voip_tariffs(
    admin: AdminPrincipal = Depends(require_admin_permission("SEE VOIP TARIFF")),
) -> list[VoipTariffView]:
    """List tariffs without prefixes, matching the native listTariffs workflow."""
    with connection() as conn:
        tariffs = PostgresVoipTariffRepository(conn).list()
    return [
        _view(tariff, include_prefixes=False, name_regex="")
        for tariff in sorted(tariffs, key=lambda item: item.name)
    ]


@router.get("/{tariff_name}", response_model=VoipTariffView)
def get_voip_tariff(
    tariff_name: str,
    include_prefixes: bool = Query(default=False),
    name_regex: str = Query(default=""),
    admin: AdminPrincipal = Depends(require_admin_permission("SEE VOIP TARIFF")),
) -> VoipTariffView:
    """Read one tariff and optionally filter its prefixes by the native name regex."""
    with connection() as conn:
        tariff = PostgresVoipTariffRepository(conn).get_by_name(tariff_name)
    if tariff is None:
        raise HTTPException(status_code=404, detail="VoIP tariff not found")
    return _view(tariff, include_prefixes=include_prefixes, name_regex=name_regex)
