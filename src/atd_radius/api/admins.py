from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_session
from atd_radius.infrastructure.admin_information import AdminInformationRepository
from atd_radius.infrastructure.db import connection

router = APIRouter(prefix="/admins", tags=["ADMIN"])


class AdminLockView(BaseModel):
    lock_id: int
    locker_admin: str | None
    reason: str | None


class AdminInformationView(BaseModel):
    admin_id: int
    username: str
    name: str | None
    comment: str | None
    deposit: str
    creator_id: int | None
    creator: str | None
    locks: list[AdminLockView]


def _can_see_admin_info(admin: AdminPrincipal) -> bool:
    return admin.permissions.is_god() or admin.permissions.has_perm("SEE ADMIN INFO")


@router.get("", response_model=list[str])
def list_admin_usernames(admin: AdminPrincipal = Depends(require_admin_session)) -> list[str]:
    # A1.24 returns all sorted names with SEE ADMIN INFO; otherwise only self.
    if not _can_see_admin_info(admin):
        return [admin.username]
    with connection() as conn:
        return AdminInformationRepository(conn).list_usernames()


@router.get("/{username}", response_model=AdminInformationView)
def get_admin_information(
    username: str,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> AdminInformationView:
    # A1.24 allows an admin to inspect their own record without SEE ADMIN INFO.
    if username != admin.username and not _can_see_admin_info(admin):
        raise HTTPException(status_code=403, detail="Administrator permission denied")
    with connection() as conn:
        record = AdminInformationRepository(conn).get_by_username(username)
    if record is None:
        raise HTTPException(status_code=404, detail="administrator not found")
    return AdminInformationView(
        admin_id=record.admin_id,
        username=record.username,
        name=record.name,
        comment=record.comment,
        deposit=str(record.deposit),
        creator_id=record.creator_id,
        creator=record.creator,
        locks=[
            AdminLockView(lock_id=lock.lock_id, locker_admin=lock.locker_admin, reason=lock.reason)
            for lock in record.locks
        ],
    )
