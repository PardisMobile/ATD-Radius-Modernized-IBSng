"""Source-backed read API for bandwidth-manager leaves used by Internet charges."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.bandwidth_manager import PostgresBandwidthLeafRepository
from atd_radius.infrastructure.db import connection

router = APIRouter(prefix="/bandwidth-manager/leaves", tags=["BANDWIDTH MANAGER"])


class BandwidthLeafView(BaseModel):
    leaf_id: int
    leaf_name: str
    interface_id: int | None
    parent_id: int | None
    default_rate_kbits: int | None
    default_ceil_kbits: int | None
    total_rate_kbits: int | None
    total_ceil_kbits: int | None


def _view(leaf) -> BandwidthLeafView:
    return BandwidthLeafView(
        leaf_id=leaf.leaf_id,
        leaf_name=leaf.leaf_name,
        interface_id=leaf.interface_id,
        parent_id=leaf.parent_id,
        default_rate_kbits=leaf.default_rate_kbits,
        default_ceil_kbits=leaf.default_ceil_kbits,
        total_rate_kbits=leaf.total_rate_kbits,
        total_ceil_kbits=leaf.total_ceil_kbits,
    )


@router.get("", response_model=list[BandwidthLeafView])
def list_bandwidth_leaves(
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE BANDWIDTH MANAGER")),
) -> list[BandwidthLeafView]:
    with connection() as conn:
        return [_view(leaf) for leaf in PostgresBandwidthLeafRepository(conn).list()]


@router.get("/{leaf_name}", response_model=BandwidthLeafView)
def get_bandwidth_leaf(
    leaf_name: str,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE BANDWIDTH MANAGER")),
) -> BandwidthLeafView:
    with connection() as conn:
        leaf = PostgresBandwidthLeafRepository(conn).get_by_name(leaf_name)
    if leaf is None:
        raise HTTPException(status_code=404, detail="Bandwidth leaf not found")
    return _view(leaf)
