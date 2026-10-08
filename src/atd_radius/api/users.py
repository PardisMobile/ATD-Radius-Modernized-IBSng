from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from atd_radius.infrastructure import UserRepository
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.user_detail import UserDetailRepository

router = APIRouter(prefix="/users", tags=["USER"])


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    locked: bool = False


class UserView(BaseModel):
    id: int
    username: str
    locked: bool


class UserListView(BaseModel):
    items: list[UserView]
    total: int
    limit: int
    offset: int


class GroupView(BaseModel):
    id: int
    name: str
    comment: str | None


class AttributeView(BaseModel):
    name: str
    value: str


class ConnectionLogView(BaseModel):
    id: int
    login_time: str | None
    logout_time: str | None
    successful: bool
    service: int | None
    ras_id: int | None
    credit_used: str | None


class NativeCredentialView(BaseModel):
    username: str
    has_password: bool


class PersistentLANView(BaseModel):
    mac: str
    ip: str
    ras_id: int | None


class UserComponentsView(BaseModel):
    normal: NativeCredentialView | None
    voip: NativeCredentialView | None
    caller_ids: list[str]
    persistent_lan: list[PersistentLANView]


class CreditChangeView(BaseModel):
    id: int
    action: int | None
    per_user_credit: str | None
    change_time: str | None
    comment: str | None


class UserDetailView(BaseModel):
    id: int
    username: str
    locked: bool
    has_password: bool
    groups: list[GroupView]
    attributes: list[AttributeView]
    components: UserComponentsView
    connection_logs: list[ConnectionLogView]
    credit_changes: list[CreditChangeView]


@router.post("", response_model=UserView, status_code=201)
def create_user(payload: UserCreate) -> UserView:
    try:
        with connection() as conn:
            repository = UserRepository(conn)
            record = repository.create(payload.username.strip(), "locked" if payload.locked else "active")
            if payload.locked:
                repository.set_status(record.id, "locked")
            conn.commit()
            return UserView(id=record.id, username=record.username, locked=record.locked)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER could not be created") from exc


@router.get("", response_model=UserListView)
def list_users(
    search: str | None = Query(default=None, max_length=255),
    status: str | None = Query(default=None, pattern="^(active|locked)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListView:
    with connection() as conn:
        repository = UserRepository(conn)
        records = repository.list(search=search, status=status, limit=limit, offset=offset)
        total = repository.count(search=search, status=status)
    return UserListView(
        items=[UserView(id=r.id, username=r.username, locked=r.locked) for r in records],
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
    return UserView(id=record.id, username=record.username, locked=record.locked)


@router.get("/{username}/detail", response_model=UserDetailView)
def get_user_detail(username: str) -> UserDetailView:
    with connection() as conn:
        repository = UserRepository(conn)
        user = repository.get_by_username(username)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        detail = UserDetailRepository(conn)
        components = UserComponentsView(
            normal=(
                NativeCredentialView(username=x[0], has_password=bool(x[1]))
                if (x := repository.normal_credentials(user.id)) is not None
                else None
            ),
            voip=(
                NativeCredentialView(username=x[0], has_password=bool(x[1]))
                if (x := repository.voip_credentials(user.id)) is not None
                else None
            ),
            caller_ids=repository.caller_ids(user.id),
            persistent_lan=[
                PersistentLANView(mac=x[0], ip=x[1], ras_id=x[2])
                for x in repository.persistent_lan(user.id)
            ],
        )
        credential = conn.execute(
            "SELECT normal_password IS NOT NULL AND normal_password <> '' FROM normal_users WHERE user_id = %s",
            (user.id,),
        ).fetchone()
        groups = detail.groups(user.id)
        attributes = detail.attributes(user.id)
        connection_logs = detail.connection_logs(user.id)
        credit_changes = detail.credit_changes(user.id)

    return UserDetailView(
        id=user.id,
        username=user.username,
        locked=user.locked,
        has_password=bool(credential[0]) if credential else False,
        groups=[GroupView(id=g.id, name=g.name, comment=g.comment) for g in groups],
        attributes=[AttributeView(name=a.name, value=a.value) for a in attributes],
        components=components,
        connection_logs=[
            ConnectionLogView(
                id=x.id,
                login_time=x.login_time,
                logout_time=x.logout_time,
                successful=x.successful,
                service=x.service,
                ras_id=x.ras_id,
                credit_used=str(x.credit_used) if x.credit_used is not None else None,
            )
            for x in connection_logs
        ],
        credit_changes=[
            CreditChangeView(
                id=x.id,
                action=x.action,
                per_user_credit=str(x.per_user_credit) if x.per_user_credit is not None else None,
                change_time=x.change_time,
                comment=x.comment,
            )
            for x in credit_changes
        ],
    )
