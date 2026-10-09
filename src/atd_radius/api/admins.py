from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from atd_radius.api.admin_dependencies import (
    AdminPrincipal,
    can_change_admin_password,
    require_admin_permission,
    require_admin_session,
)
from atd_radius.domain.ibsng_password import hash_ibsng_password
from atd_radius.infrastructure.admin_credentials import AdminCredentialRepository
from atd_radius.infrastructure.admin_information import AdminInformationRepository
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository

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


class AdminInformationUpdate(BaseModel):
    name: str
    comment: str


@router.put("/{username}", response_model=AdminInformationView)
def update_admin_information(
    username: str,
    payload: AdminInformationUpdate,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE ADMIN INFO")),
) -> AdminInformationView:
    if admin.remote_addr is not None:
        try:
            remote_addr = str(ipaddress.ip_address(admin.remote_addr))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc
    else:
        remote_addr = None

    try:
        with connection() as conn:
            repository = AdminInformationRepository(conn)
            updated = repository.update_info(username, payload.name, payload.comment)
            if updated is None:
                raise HTTPException(status_code=404, detail="administrator not found")
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="admin.info.update",
                outcome="success",
                target_type="admin",
                target_id=str(updated.admin_id),
                remote_addr=remote_addr,
                details={"target_username": updated.username, "name": payload.name, "comment": payload.comment},
            )
            conn.commit()
            return _admin_information_view(updated)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Administrator information could not be updated") from exc


class AdminPasswordChange(BaseModel):
    new_password: str


@router.put("/{username}/password", status_code=204)
def change_admin_password(
    username: str,
    payload: AdminPasswordChange,
    admin: AdminPrincipal = Depends(require_admin_session),
):
    # Source: AdminHandler.changePassword; self-change is allowed without the
    # CHANGE ADMIN PASSWORD permission, but changing another admin is not.
    if not can_change_admin_password(admin, username):
        raise HTTPException(status_code=403, detail="Administrator permission denied")
    normalized_password = payload.new_password.strip()
    try:
        password_hash = hash_ibsng_password(normalized_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Password contains unsupported characters") from exc
    remote_addr = _validated_remote_addr(admin.remote_addr)
    try:
        with connection() as conn:
            target = AdminCredentialRepository(conn).update_password(username, password_hash)
            if target is None:
                raise HTTPException(status_code=404, detail="administrator not found")
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="admin.password.change",
                outcome="success",
                target_type="admin",
                target_id=str(target.admin_id),
                remote_addr=remote_addr,
                details={"target_username": target.username, "self_change": target.username == admin.username},
            )
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Administrator password could not be changed") from exc
    from fastapi import Response
    return Response(status_code=204)


class AdminLockCreate(BaseModel):
    reason: str


def _validated_remote_addr(remote_addr: str | None) -> str | None:
    if remote_addr is None:
        return None
    try:
        return str(ipaddress.ip_address(remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc


def _admin_information_view(record) -> AdminInformationView:
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


@router.post("/{username}/locks", response_model=AdminInformationView)
def lock_admin(
    username: str,
    payload: AdminLockCreate,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE ADMIN INFO")),
) -> AdminInformationView:
    remote_addr = _validated_remote_addr(admin.remote_addr)
    try:
        with connection() as conn:
            repository = AdminInformationRepository(conn)
            updated = repository.lock_admin(username, reason=payload.reason, locker_admin_id=admin.admin_id)
            if updated is None:
                raise HTTPException(status_code=404, detail="administrator not found")
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id, actor_username=admin.username,
                action="admin.lock", outcome="success", target_type="admin",
                target_id=str(updated.admin_id), remote_addr=remote_addr,
                details={"target_username": updated.username, "reason": payload.reason, "lock_count": len(updated.locks)},
            )
            conn.commit()
            return _admin_information_view(updated)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Administrator could not be locked") from exc


@router.delete("/{username}/locks/{lock_id}", response_model=AdminInformationView)
def unlock_admin(
    username: str,
    lock_id: int,
    admin: AdminPrincipal = Depends(require_admin_permission("CHANGE ADMIN INFO")),
) -> AdminInformationView:
    if lock_id <= 0:
        raise HTTPException(status_code=422, detail="lock_id must be positive")
    remote_addr = _validated_remote_addr(admin.remote_addr)
    try:
        with connection() as conn:
            repository = AdminInformationRepository(conn)
            updated = repository.unlock_admin(username, lock_id)
            if updated is None:
                raise HTTPException(status_code=404, detail="administrator or lock not found")
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id, actor_username=admin.username,
                action="admin.unlock", outcome="success", target_type="admin",
                target_id=str(updated.admin_id), remote_addr=remote_addr,
                details={"target_username": updated.username, "lock_id": lock_id},
            )
            conn.commit()
            return _admin_information_view(updated)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Administrator lock could not be removed") from exc


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
