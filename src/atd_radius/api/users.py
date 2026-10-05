from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    status: str = Field(default="active", pattern="^(active|disabled|expired|locked)$")


class UserView(BaseModel):
    id: UUID
    username: str
    status: str


@router.post("", response_model=UserView, status_code=201)
def create_user(payload: UserCreate) -> UserView:
    try:
        with connection() as conn:
            record = UserRepository(conn).create(payload.username, payload.status)
            conn.commit()
            return UserView(id=record.id, username=record.username, status=record.status)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="user could not be created") from exc


@router.get("/{username}", response_model=UserView)
def get_user(username: str) -> UserView:
    with connection() as conn:
        record = UserRepository(conn).get_by_username(username)
    if record is None:
        raise HTTPException(status_code=404, detail="user not found")
    return UserView(id=record.id, username=record.username, status=record.status)
