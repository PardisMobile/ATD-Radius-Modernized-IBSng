from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.group import GroupRepository

router = APIRouter(prefix="/groups", tags=["GROUP"])


class GroupCreate(BaseModel):
    group_name: str = Field(min_length=1, max_length=255)
    comment: str | None = None
    owner_id: int = Field(ge=1)


class GroupUpdate(GroupCreate):
    pass


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
def list_groups() -> list[GroupView]:
    with connection() as conn:
        records = GroupRepository(conn).list()
    return [GroupView(group_id=x.id, group_name=x.name, owner_id=x.owner_id, comment=x.comment) for x in records]


@router.post("", response_model=GroupView, status_code=201)
def add_new_group(payload: GroupCreate) -> GroupView:
    try:
        with connection() as conn:
            repository = GroupRepository(conn)
            if repository.get_by_name(payload.group_name) is not None:
                raise ValueError("group name already exists")
            record = repository.create(payload.group_name, payload.comment, payload.owner_id)
            conn.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail="GROUP could not be created") from exc
    return GroupView(group_id=record.id, group_name=record.name, owner_id=record.owner_id, comment=record.comment)


@router.get("/{group_name}", response_model=GroupInfoView)
def get_group_info(group_name: str) -> GroupInfoView:
    with connection() as conn:
        repository = GroupRepository(conn)
        record = repository.get_by_name(group_name)
        if record is None:
            raise HTTPException(status_code=404, detail="group not found")
        attrs = repository.attributes(record.id)
    return GroupInfoView(
        group_id=record.id,
        group_name=record.name,
        owner_id=record.owner_id,
        comment=record.comment,
        attrs=[GroupAttributeView(attr_name=x.name, attr_value=x.value) for x in attrs],
    )


@router.put("/{group_id}", response_model=GroupView)
def update_group(group_id: int, payload: GroupUpdate) -> GroupView:
    try:
        with connection() as conn:
            repository = GroupRepository(conn)
            record = repository.update(group_id, payload.group_name, payload.comment, payload.owner_id)
            conn.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="group not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GroupView(group_id=record.id, group_name=record.name, owner_id=record.owner_id, comment=record.comment)


@router.patch("/{group_id}/attributes/{attr_name}", response_model=GroupInfoView)
def update_group_attribute(group_id: int, attr_name: str, payload: GroupAttributePayload) -> GroupInfoView:
    with connection() as conn:
        repository = GroupRepository(conn)
        if repository.get(group_id) is None:
            raise HTTPException(status_code=404, detail="group not found")
        repository.set_attribute(group_id, attr_name, payload.attr_value)
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
def delete_group(group_name: str) -> None:
    try:
        with connection() as conn:
            repository = GroupRepository(conn)
            record = repository.get_by_name(group_name)
            if record is None:
                raise LookupError("group not found")
            repository.delete(record.id)
            conn.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="group not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
