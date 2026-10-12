"""Source-backed read API for native A1.24 bandwidth-manager data."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.bandwidth_manager import (
    BandwidthTree,
    BandwidthTreeCorruptError,
    PostgresBandwidthLeafRepository,
    PostgresBandwidthManagerRepository,
)
from atd_radius.infrastructure.db import connection

router = APIRouter(prefix="/bandwidth-manager", tags=["BANDWIDTH MANAGER"])


class BandwidthLeafView(BaseModel):
    leaf_id: int
    leaf_name: str
    interface_id: int | None
    parent_id: int | None
    default_rate_kbits: int | None
    default_ceil_kbits: int | None
    total_rate_kbits: int | None
    total_ceil_kbits: int | None


class BandwidthInterfaceView(BaseModel):
    interface_id: int
    interface_name: str
    comment: str


class BandwidthNodeView(BaseModel):
    node_id: int
    interface_id: int
    parent_id: int | None
    rate_kbits: int | None
    ceil_kbits: int | None


class BandwidthTreeView(BaseModel):
    node_id: int
    children: list[BandwidthTreeView] = Field(default_factory=list)
    leaves: list[str] = Field(default_factory=list)


BandwidthTreeView.model_rebuild()


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


def _tree_view(tree: BandwidthTree) -> BandwidthTreeView:
    return BandwidthTreeView(
        node_id=tree.node_id,
        children=[_tree_view(child) for child in tree.children],
        leaves=list(tree.leaves),
    )


@router.get("/interfaces", response_model=list[BandwidthInterfaceView])
def list_bandwidth_interfaces(
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE BANDWIDTH MANAGER")),
) -> list[BandwidthInterfaceView]:
    with connection() as conn:
        interfaces = PostgresBandwidthManagerRepository(conn).list_interfaces()
    return [
        BandwidthInterfaceView(
            interface_id=item.interface_id,
            interface_name=item.interface_name,
            comment=item.comment,
        )
        for item in interfaces
    ]


@router.get("/interfaces/{interface_name}/tree", response_model=BandwidthTreeView)
def get_bandwidth_tree(
    interface_name: str,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE BANDWIDTH MANAGER")),
) -> BandwidthTreeView:
    try:
        with connection() as conn:
            repo = PostgresBandwidthManagerRepository(conn)
            interface = repo.get_interface_by_name(interface_name)
            if interface is None:
                raise HTTPException(status_code=404, detail="Bandwidth interface not found")
            tree = repo.get_tree(interface.interface_id)
    except BandwidthTreeCorruptError as exc:
        raise HTTPException(status_code=409, detail="Bandwidth tree contains a cycle") from exc
    if tree is None:
        raise HTTPException(status_code=404, detail="Bandwidth interface has no root node")
    return _tree_view(tree)


@router.get("/nodes/{node_id}", response_model=BandwidthNodeView)
def get_bandwidth_node(
    node_id: int,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE BANDWIDTH MANAGER")),
) -> BandwidthNodeView:
    with connection() as conn:
        node = PostgresBandwidthManagerRepository(conn).get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Bandwidth node not found")
    return BandwidthNodeView(
        node_id=node.node_id,
        interface_id=node.interface_id,
        parent_id=node.parent_id,
        rate_kbits=node.rate_kbits,
        ceil_kbits=node.ceil_kbits,
    )


@router.get("/leaves", response_model=list[BandwidthLeafView])
def list_bandwidth_leaves(
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE BANDWIDTH MANAGER")),
) -> list[BandwidthLeafView]:
    with connection() as conn:
        return [_view(leaf) for leaf in PostgresBandwidthLeafRepository(conn).list()]


@router.get("/leaves/{leaf_name}", response_model=BandwidthLeafView)
def get_bandwidth_leaf(
    leaf_name: str,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE BANDWIDTH MANAGER")),
) -> BandwidthLeafView:
    with connection() as conn:
        leaf = PostgresBandwidthLeafRepository(conn).get_by_name(leaf_name)
    if leaf is None:
        raise HTTPException(status_code=404, detail="Bandwidth leaf not found")
    return _view(leaf)
