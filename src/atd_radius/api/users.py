from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from atd_radius.infrastructure import UserRepository
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.user_detail import UserDetailRepository

router = APIRouter(prefix="/users", tags=["users"])


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
    description: str | None
    enabled: bool


class ServiceView(BaseModel):
    id: UUID
    name: str
    description: str | None
    enabled: bool
    assignment_enabled: bool
    starts_at: str | None
    expires_at: str | None


class AttributeView(BaseModel):
    name: str
    value: str
    operator: str
    value_type: str
    scope_type: str
    precedence: int
    enabled: bool


class SessionView(BaseModel):
    id: UUID
    session_key: str
    ras_name: str | None
    framed_ip: str | None
    started_at: str | None
    last_interim_at: str | None
    input_octets: int
    output_octets: int


class CreditView(BaseModel):
    amount: str
    currency: str
    kind: str
    reference: str | None
    created_at: str


class UserDetailView(BaseModel):
    id: UUID
    username: str
    locked: bool
    credential_enabled: bool
    has_password: bool
    groups: list[GroupView]
    services: list[ServiceView]
    attributes: list[AttributeView]
    active_sessions: list[SessionView]
    credit_ledger: list[CreditView]


@router.post("", response_model=UserView, status_code=201)
def create_user(payload: UserCreate) -> UserView:
    try:
        with connection() as conn:
            record = UserRepository(conn).create(payload.username.strip(), 'locked' if payload.locked else 'active')
            conn.commit()
            return UserView(id=record.id, username=record.username, status=record.status)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="user could not be created") from exc


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
    return UserView(id=record.id, username=record.username, status=record.status)


@router.get("/{username}/detail", response_model=UserDetailView)
def get_user_detail(username: str) -> UserDetailView:
    with connection() as conn:
        user = UserRepository(conn).get_by_username(username)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        detail = UserDetailRepository(conn)
        credential = conn.execute(
            "SELECT normal_password IS NOT NULL AND normal_password <> '' FROM normal_users WHERE user_id = %s",
            (user.id,),
        ).fetchone()
        groups = detail.groups(user.id)
        services = detail.services(user.id)
        attributes = detail.attributes(user.id)
        sessions = detail.active_sessions(user.id)
        credit = detail.credit_ledger(user.id)

    return UserDetailView(
        id=user.id,
        username=user.username,
        locked=user.locked,
        credential_enabled=bool(credential[0]) if credential else False,
        has_password=bool(credential[1]) if credential else False,
        groups=[GroupView(id=g.id, name=g.name, description=g.description, enabled=g.enabled) for g in groups],
        services=[
            ServiceView(
                id=s.id,
                name=s.name,
                description=s.description,
                enabled=s.enabled,
                assignment_enabled=s.assignment_enabled,
                starts_at=s.starts_at.isoformat() if s.starts_at else None,
                expires_at=s.expires_at.isoformat() if s.expires_at else None,
            )
            for s in services
        ],
        attributes=[AttributeView(**a.__dict__) for a in attributes],
        active_sessions=[
            SessionView(
                id=s.id,
                session_key=s.session_key,
                ras_name=s.ras_name,
                framed_ip=s.framed_ip,
                started_at=s.started_at.isoformat() if s.started_at else None,
                last_interim_at=s.last_interim_at.isoformat() if s.last_interim_at else None,
                input_octets=s.input_octets,
                output_octets=s.output_octets,
            )
            for s in sessions
        ],
        credit_ledger=[
            CreditView(
                amount=str(c.amount),
                currency=c.currency,
                kind=c.kind,
                reference=c.reference,
                created_at=c.created_at.isoformat(),
            )
            for c in credit
        ],
    )
