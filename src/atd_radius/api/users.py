from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from atd_radius.infrastructure import UserRepository
from atd_radius.infrastructure.db import connection

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    status: str = Field(default="active", pattern="^(active|disabled|expired|locked)$")


class UserView(BaseModel):
    id: UUID
    username: str
    status: str


class UserListView(BaseModel):
    items: list[UserView]
    total: int
    limit: int
    offset: int


@router.post("", response_model=UserView, status_code=201)
def create_user(payload: UserCreate) -> UserView:
    try:
        with connection() as conn:
            record = UserRepository(conn).create(payload.username.strip(), payload.status)
            conn.commit()
            return UserView(id=record.id, username=record.username, status=record.status)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="user could not be created") from exc


@router.get("", response_model=UserListView)
def list_users(
    search: str | None = Query(default=None, max_length=255),
    status: str | None = Query(default=None, pattern="^(active|disabled|expired|locked)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListView:
    with connection() as conn:
        repository = UserRepository(conn)
        records = repository.list(search=search, status=status, limit=limit, offset=offset)
        total = repository.count(search=search, status=status)
    return UserListView(
        items=[UserView(id=r.id, username=r.username, status=r.status) for r in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{username}", response_model=UserView)
def get_user(username: str) -> UserView:
    with connection() as conn:
        record = UserRepository(conn).get_by_username(username)
    if record is None:
        raise HTTPException(status_code=404, detail="user not found")
    return UserView(id=record.id, username=record.username, status=record.status)
