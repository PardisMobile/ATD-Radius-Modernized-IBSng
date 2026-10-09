from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import AdminPrincipal, can_use_group, require_admin_permission, require_admin_session, require_group_change
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository
from atd_radius.infrastructure.group import GroupRepository

router = APIRouter(prefix="/groups", tags=["GROUP"])


def _audit(conn, admin: AdminPrincipal, action: str, target_type: str, target_id: str) -> None:
    OperationalAuditRepository(conn).append(
        actor_admin_id=admin.admin_id,
        actor_username=admin.username,
        action=action,
        outcome="success",
        target_type=target_type,
        target_id=target_id,
        remote_addr=admin.remote_addr,
    )


class GroupCreate(BaseModel):
    group_name: str = Field(min_length=1, max_length=255)
    comment: str | None = None


class GroupUpdate(GroupCreate):
    owner_id: int = Field(ge=1)


class GroupView(BaseModel):
    group_id: int
    group_name: str
    owner_id: int | None
    comment: str | None


class GroupAttributeView(BaseModel):
    attr_name: str
    attr_value: str


class GroupAttributePayload(BaseModel):
    attr_value: str


class GroupInfoView(GroupView):
    attrs: list[GroupAttributeView]


@router.get("", response_model=list[GroupView])
def list_groups(admin: AdminPrincipal = Depends(require_admin_session)) -> list[GroupView]:
    with connection() as conn:
        records = GroupRepository(conn).list()
    visible = [x for x in records if can_use_group(admin, x.name, x.owner_id)]
    return [GroupView(group_id=x.id, group_name=x.name, owner_id=x.owner_id, comment=x.comment) for x in visible]


@router.post("", response_model=GroupView, status_code=201)
def add_new_group(payload: GroupCreate, admin: AdminPrincipal = Depends(require_admin_permission("ADD NEW GROUP"))) -> GroupView:
    try:
        with connection() as conn:
            repository = GroupRepository(conn)
            if repository.get_by_name(payload.group_name) is not None:
                raise ValueError("group name already exists")
            record = repository.create(payload.group_name, payload.comment, admin.admin_id)
            _audit(conn, admin, "group.create", "group", str(record.id))
            conn.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail="GROUP could not be created") from exc
    return GroupView(group_id=record.id, group_name=record.name, owner_id=record.owner_id, comment=record.comment)


@router.get("/{group_name}", response_model=GroupInfoView)
def get_group_info(group_name: str, admin: AdminPrincipal = Depends(require_admin_session)) -> GroupInfoView:
    with connection() as conn:
        repository = GroupRepository(conn)
        record = repository.get_by_name(group_name)
        if record is None:
            raise HTTPException(status_code=404, detail="group not found")
        if not can_use_group(admin, record.name, record.owner_id):
            raise HTTPException(status_code=403, detail="Administrator group access denied")
        attrs = repository.attributes(record.id)
    return GroupInfoView(
        group_id=record.id,
        group_name=record.name,
        owner_id=record.owner_id,
        comment=record.comment,
        attrs=[GroupAttributeView(attr_name=x.name, attr_value=x.value) for x in attrs],
    )


@router.put("/{group_id}", response_model=GroupView)
def update_group(group_id: int, payload: GroupUpdate, admin: AdminPrincipal = Depends(require_group_change())) -> GroupView:
    try:
        with connection() as conn:
            repository = GroupRepository(conn)
            record = repository.update(group_id, payload.group_name, payload.comment, payload.owner_id)
            _audit(conn, admin, "group.update", "group", str(group_id))
            conn.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="group not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GroupView(group_id=record.id, group_name=record.name, owner_id=record.owner_id, comment=record.comment)


@router.patch("/{group_id}/attributes/{attr_name}", response_model=GroupInfoView)
def update_group_attribute(group_id: int, attr_name: str, payload: GroupAttributePayload, admin: AdminPrincipal = Depends(require_group_change())) -> GroupInfoView:
    with connection() as conn:
        repository = GroupRepository(conn)
        if repository.get(group_id) is None:
            raise HTTPException(status_code=404, detail="group not found")
        repository.set_attribute(group_id, attr_name, payload.attr_value)
        _audit(conn, admin, "group.attribute.set", "group_attribute", f"{group_id}:{attr_name}")
        conn.commit()
        record = repository.get(group_id)
        attrs = repository.attributes(group_id)
    return GroupInfoView(
        group_id=record.id,
        group_name=record.name,
        owner_id=record.owner_id,
        comment=record.comment,
        attrs=[GroupAttributeView(attr_name=x.name, attr_value=x.value) for x in attrs],
    )


@router.delete("/{group_name}", status_code=204)
def delete_group(group_name: str, admin: AdminPrincipal = Depends(require_admin_permission("ADD NEW GROUP"))) -> None:
    try:
        with connection() as conn:
            repository = GroupRepository(conn)
            record = repository.get_by_name(group_name)
            if record is None:
                raise LookupError("group not found")
            repository.delete(record.id)
            _audit(conn, admin, "group.delete", "group", str(record.id))
            conn.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="group not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
