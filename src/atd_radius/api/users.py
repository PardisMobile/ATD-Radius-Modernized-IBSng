from __future__ import annotations

import ipaddress
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import (
    AdminPrincipal,
    can_access_user,
    can_change_user,
    can_change_user_credit,
    can_change_voip_user_attributes,
    can_use_group,
    can_view_connection_logs,
    can_view_credit_changes,
    require_admin_permission,
    require_admin_session,
)
from atd_radius.infrastructure import UserRepository
from atd_radius.infrastructure.credit_repository import (
    CreditUnderflowError,
    InsufficientAdminDepositError,
    UserCreditRepository,
)
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.group import GroupRepository
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository
from atd_radius.infrastructure.user_detail import UserDetailRepository
from atd_radius.infrastructure.user_attribute_mutations import (
    UserAttributeMutationError,
    UserAttributeMutationRepository,
)
from atd_radius.infrastructure.caller_id_mutations import CallerIDMutationRepository

router = APIRouter(prefix="/users", tags=["USER"])


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    group_id: int = Field(gt=0)
    locked: bool = False
    initial_credit: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    credit_comment: str = Field(default="", max_length=1000)


class UserAttributeMutation(BaseModel):
    attrs: dict[str, str] = Field(default_factory=dict)
    to_delete: list[str] = Field(default_factory=list)


class UserAttributeMutationView(BaseModel):
    id: int
    username: str
    attributes: list[AttributeView]


class UserOwnerChange(BaseModel):
    owner_username: str = Field(min_length=1, max_length=255)


class UserOwnerView(BaseModel):
    id: int
    username: str
    owner_username: str


class UserGroupChange(BaseModel):
    group_name: str = Field(min_length=1, max_length=255)


class UserGroupView(BaseModel):
    id: int
    username: str
    group_name: str
    previous_group_name: str


class UserCallerIDsChange(BaseModel):
    caller_ids: str = Field(min_length=1, max_length=100000)


class UserCallerIDsView(BaseModel):
    id: int
    username: str
    caller_ids: list[str]


class UserCreditChange(BaseModel):
    delta: Decimal = Field(max_digits=12, decimal_places=2)
    comment: str = Field(max_length=1000)


class UserCreditBulkChange(UserCreditChange):
    usernames: list[str] = Field(min_length=1, max_length=100)


class UserCreditView(BaseModel):
    user_id: int
    username: str
    credit: Decimal


class UserCreditBulkView(BaseModel):
    items: list[UserCreditView]
    delta: Decimal
    total_admin_credit: Decimal


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
    connection_logs: list[ConnectionLogView] | None
    credit_changes: list[CreditChangeView] | None


@router.post("", response_model=UserView, status_code=201)
def create_user(payload: UserCreate, admin: AdminPrincipal = Depends(require_admin_permission("ADD NEW USER"))) -> UserView:
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    try:
        with connection() as conn:
            group_repo = GroupRepository(conn)
            group = group_repo.get(payload.group_id)
            if group is None:
                raise HTTPException(status_code=404, detail="group not found")
            if not can_use_group(admin, group.name, group.owner_id):
                raise HTTPException(status_code=403, detail="Administrator group access denied")
            repository = UserRepository(conn)
            record = repository.create(
                payload.username.strip(),
                "locked" if payload.locked else "active",
                owner_id=admin.admin_id,
                group_id=payload.group_id,
                initial_credit=payload.initial_credit,
            )
            if payload.locked:
                repository.set_status(record.id, "locked")
            try:
                UserCreditRepository(conn).record_user_creation_credit(
                    record.id,
                    admin_id=admin.admin_id,
                    admin_username=admin.username,
                    credit=payload.initial_credit,
                    remote_addr=remote_addr,
                    comment=payload.credit_comment,
                    allow_negative_deposit=(
                        admin.permissions.is_god()
                        or admin.permissions.has_perm("NO DEPOSIT LIMIT")
                    ),
                )
            except InsufficientAdminDepositError as exc:
                raise HTTPException(status_code=403, detail="Administrator deposit is insufficient") from exc

            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="user.create",
                outcome="success",
                target_type="user",
                target_id=str(record.id),
                remote_addr=remote_addr,
                details={
                    "group_id": payload.group_id,
                    "locked": payload.locked,
                    "initial_credit": str(payload.initial_credit),
                    "credit_comment": payload.credit_comment,
                },
            )
            conn.commit()
            return UserView(id=record.id, username=record.username, locked=payload.locked)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER could not be created") from exc


@router.get("", response_model=UserListView)
def list_users(
    search: str | None = Query(default=None, max_length=255),
    status: str | None = Query(default=None, pattern="^(active|locked)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: AdminPrincipal = Depends(require_admin_session),
) -> UserListView:
    if not can_access_user(admin, admin.admin_id):
        raise HTTPException(status_code=403, detail="Administrator permission denied")
    owner_filter = None if admin.permissions.is_god() or admin.permissions.values.get("GET USER INFORMATION") == "All" else admin.admin_id
    with connection() as conn:
        repository = UserRepository(conn)
        records = repository.list(search=search, status=status, limit=limit, offset=offset, owner_id=owner_filter)
        total = repository.count(search=search, status=status, owner_id=owner_filter)
    return UserListView(
        items=[UserView(id=r.id, username=r.username, locked=r.locked) for r in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{username}", response_model=UserView)
def get_user(username: str, admin: AdminPrincipal = Depends(require_admin_session)) -> UserView:
    with connection() as conn:
        record = UserRepository(conn).get_by_username(username)
    if record is None:
        raise HTTPException(status_code=404, detail="user not found")
    if not can_access_user(admin, record.owner_id):
        raise HTTPException(status_code=403, detail="Administrator permission denied")
    return UserView(id=record.id, username=record.username, locked=record.locked)


@router.get("/{username}/detail", response_model=UserDetailView)
def get_user_detail(username: str, admin: AdminPrincipal = Depends(require_admin_session)) -> UserDetailView:
    with connection() as conn:
        repository = UserRepository(conn)
        user = repository.get_by_username(username)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        if not can_access_user(admin, user.owner_id):
            raise HTTPException(status_code=403, detail="Administrator permission denied")
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
        can_see_connections = can_view_connection_logs(admin, user.owner_id)
        can_see_credit_changes = can_view_credit_changes(admin, user.owner_id)
        connection_logs = detail.connection_logs(user.id) if can_see_connections else None
        credit_changes = detail.credit_changes(user.id) if can_see_credit_changes else None

    return UserDetailView(
        id=user.id,
        username=user.username,
        locked=user.locked,
        has_password=bool(credential[0]) if credential else False,
        groups=[GroupView(id=g.id, name=g.name, comment=g.comment) for g in groups],
        attributes=[AttributeView(name=a.name, value=a.value) for a in attributes],
        components=components,
        connection_logs=(
            [
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
            ]
            if connection_logs is not None
            else None
        ),
        credit_changes=(
            [
                CreditChangeView(
                    id=x.id,
                    action=x.action,
                    per_user_credit=str(x.per_user_credit) if x.per_user_credit is not None else None,
                    change_time=x.change_time,
                    comment=x.comment,
                )
                for x in credit_changes
            ]
            if credit_changes is not None
            else None
        ),
    )


@router.put("/{username}/attributes", response_model=UserAttributeMutationView)
def mutate_user_attributes(
    username: str,
    payload: UserAttributeMutation,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> UserAttributeMutationView:
    """Mutate only attributes handled by A1.24's generic comment plugin."""
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    try:
        with connection() as conn:
            repository = UserAttributeMutationRepository(conn)
            target = repository.lock_target(username)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            if not can_change_user(admin, target.owner_id):
                raise HTTPException(status_code=403, detail="Administrator permission denied")
            try:
                result = repository.apply(
                    target,
                    admin_id=admin.admin_id,
                    attrs=payload.attrs,
                    to_delete=payload.to_delete,
                )
            except UserAttributeMutationError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="user.attributes.mutate",
                outcome="success",
                target_type="user",
                target_id=str(target.user_id),
                remote_addr=remote_addr,
                details={
                    "changed_attributes": sorted(payload.attrs),
                    "deleted_attributes": sorted(payload.to_delete),
                },
            )
            conn.commit()
            return UserAttributeMutationView(
                id=result.user_id,
                username=result.username,
                attributes=[
                    AttributeView(name=name, value=value)
                    for name, value in result.attributes
                ],
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER attributes could not be changed") from exc


@router.put("/{username}/group", response_model=UserGroupView)
def change_user_group(
    username: str,
    payload: UserGroupChange,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> UserGroupView:
    """Implement A1.24's special group_name updater on users.group_id."""
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    group_name = payload.group_name.strip()
    if not group_name:
        raise HTTPException(status_code=422, detail="group_name must not be empty")

    try:
        with connection() as conn:
            repository = UserAttributeMutationRepository(conn)
            target = repository.lock_target(username)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            if not can_change_user(admin, target.owner_id):
                raise HTTPException(status_code=403, detail="Administrator permission denied")

            group = GroupRepository(conn).get_by_name_for_share(group_name)
            if group is None:
                raise HTTPException(status_code=404, detail="group not found")
            if not can_use_group(admin, group.name, group.owner_id):
                raise HTTPException(status_code=403, detail="Administrator group access denied")

            previous_group_name = repository.change_group(
                target,
                admin_id=admin.admin_id,
                group_id=group.id,
                group_name=group.name,
            )
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="user.group.change",
                outcome="success",
                target_type="user",
                target_id=str(target.user_id),
                remote_addr=remote_addr,
                details={
                    "previous_group": previous_group_name,
                    "new_group": group.name,
                },
            )
            conn.commit()
            return UserGroupView(
                id=target.user_id,
                username=target.username,
                group_name=group.name,
                previous_group_name=previous_group_name,
            )
    except HTTPException:
        raise
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="group not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER group could not be changed") from exc


@router.put("/{username}/owner", response_model=UserOwnerView)
def change_user_owner(
    username: str,
    payload: UserOwnerChange,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> UserOwnerView:
    """Implement A1.24's owner_name updater with its separate permission check."""
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    owner_username = payload.owner_username.strip()
    if not owner_username:
        raise HTTPException(status_code=422, detail="owner_username must not be empty")

    try:
        with connection() as conn:
            repository = UserAttributeMutationRepository(conn)
            target = repository.lock_target(username)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            if not can_change_user(admin, target.owner_id):
                raise HTTPException(status_code=403, detail="Administrator permission denied")
            if (
                owner_username != admin.username
                and not admin.permissions.is_god()
                and not admin.permissions.has_perm("CHANGE USERS OWNER")
            ):
                raise HTTPException(status_code=403, detail="Administrator owner-transfer permission denied")
            try:
                new_owner = repository.change_owner(
                    target,
                    admin_id=admin.admin_id,
                    owner_username=owner_username,
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail="owner administrator not found") from exc

            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="user.owner.change",
                outcome="success",
                target_type="user",
                target_id=str(target.user_id),
                remote_addr=remote_addr,
                details={
                    "previous_owner": target.owner_username,
                    "new_owner": new_owner,
                },
            )
            conn.commit()
            return UserOwnerView(
                id=target.user_id,
                username=target.username,
                owner_username=new_owner,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER owner could not be changed") from exc


@router.put("/{username}/caller-ids", response_model=UserCallerIDsView)
def change_user_caller_ids(
    username: str,
    payload: UserCallerIDsChange,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> UserCallerIDsView:
    """Apply A1.24 caller_id plugin semantics to caller_id_users, never user_attrs."""
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    try:
        with connection() as conn:
            repository = CallerIDMutationRepository(conn)
            target = repository.lock_target(username)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            if not can_change_voip_user_attributes(admin, target.owner_id):
                raise HTTPException(status_code=403, detail="Administrator permission denied")
            try:
                caller_ids = repository.change(
                    target, admin_id=admin.admin_id, expression=payload.caller_ids
                )
            except UserAttributeMutationError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="user.caller_ids.change",
                outcome="success",
                target_type="user",
                target_id=str(target.user_id),
                remote_addr=remote_addr,
                details={"caller_ids": caller_ids},
            )
            conn.commit()
            return UserCallerIDsView(id=target.user_id, username=target.username, caller_ids=caller_ids)
    except HTTPException:
        raise
    except UserAttributeMutationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER caller IDs could not be changed") from exc


@router.delete("/{username}/caller-ids", response_model=UserCallerIDsView)
def delete_user_caller_ids(
    username: str,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> UserCallerIDsView:
    """Apply the A1.24 caller_id updater's delete path and native audit semantics."""
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc
    try:
        with connection() as conn:
            repository = UserAttributeMutationRepository(conn)
            target = repository.lock_target(username)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            if not can_change_voip_user_attributes(admin, target.owner_id):
                raise HTTPException(status_code=403, detail="Administrator permission denied")
            old_ids = repository.delete(target, admin_id=admin.admin_id)
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="user.caller_ids.delete",
                outcome="success",
                target_type="user",
                target_id=str(target.user_id),
                remote_addr=remote_addr,
                details={"deleted_caller_ids": old_ids},
            )
            conn.commit()
            return UserCallerIDsView(id=target.user_id, username=target.username, caller_ids=[])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER caller IDs could not be deleted") from exc


@router.post("/{username}/credit", response_model=UserCreditView)
def change_user_credit(
    username: str,
    payload: UserCreditChange,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> UserCreditView:
    """Apply one source-backed A1.24 credit change as a single audited transaction."""
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    try:
        with connection() as conn:
            repository = UserCreditRepository(conn)
            target = repository.lock_target(username)
            if target is None:
                raise HTTPException(status_code=404, detail="user not found")
            if not can_change_user_credit(admin, target.owner_id):
                raise HTTPException(status_code=403, detail="Administrator permission denied")
            try:
                credit = repository.apply_admin_change(
                    target,
                    admin_id=admin.admin_id,
                    admin_username=admin.username,
                    delta=payload.delta,
                    remote_addr=remote_addr,
                    comment=payload.comment,
                    allow_negative_deposit=(
                        admin.permissions.is_god()
                        or admin.permissions.has_perm("NO DEPOSIT LIMIT")
                    ),
                )
            except CreditUnderflowError as exc:
                raise HTTPException(status_code=409, detail="User credit cannot become negative") from exc
            except InsufficientAdminDepositError as exc:
                raise HTTPException(status_code=403, detail="Administrator deposit is insufficient") from exc

            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="user.credit.change",
                outcome="success",
                target_type="user",
                target_id=str(target.user_id),
                remote_addr=remote_addr,
                details={"delta": str(payload.delta), "resulting_credit": str(credit)},
            )
            conn.commit()
            return UserCreditView(user_id=target.user_id, username=target.username, credit=credit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER credit could not be changed") from exc

@router.post("/credit/bulk", response_model=UserCreditBulkView)
def change_users_credit_bulk(
    payload: UserCreditBulkChange,
    admin: AdminPrincipal = Depends(require_admin_session),
) -> UserCreditBulkView:
    """Apply one A1.24-style per-user credit delta to a bounded batch."""
    usernames = [name.strip() for name in payload.usernames]
    if any(not name or len(name) > 255 for name in usernames):
        raise HTTPException(status_code=422, detail="Each username must contain 1 to 255 characters")
    if len(set(usernames)) != len(usernames):
        raise HTTPException(status_code=422, detail="Duplicate usernames are not allowed")
    if admin.remote_addr is None:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required")
    try:
        remote_addr = str(ipaddress.ip_address(admin.remote_addr))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid administrator remote address is required") from exc

    try:
        with connection() as conn:
            repository = UserCreditRepository(conn)
            targets = repository.lock_targets(usernames)
            if len(targets) != len(usernames):
                raise HTTPException(status_code=404, detail="One or more users were not found")
            if any(not can_change_user_credit(admin, target.owner_id) for target in targets):
                raise HTTPException(status_code=403, detail="Administrator permission denied")
            try:
                credits = repository.apply_admin_change_many(
                    targets,
                    admin_id=admin.admin_id,
                    admin_username=admin.username,
                    delta=payload.delta,
                    remote_addr=remote_addr,
                    comment=payload.comment,
                    allow_negative_deposit=(
                        admin.permissions.is_god()
                        or admin.permissions.has_perm("NO DEPOSIT LIMIT")
                    ),
                )
            except CreditUnderflowError as exc:
                raise HTTPException(status_code=409, detail="A user credit cannot become negative") from exc
            except InsufficientAdminDepositError as exc:
                raise HTTPException(status_code=403, detail="Administrator deposit is insufficient") from exc

            total_admin_credit = payload.delta * len(targets)
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="user.credit.change_bulk",
                outcome="success",
                target_type="user_batch",
                target_id=f"{len(targets)} users",
                remote_addr=remote_addr,
                details={
                    "user_ids": [target.user_id for target in targets],
                    "usernames": [target.username for target in targets],
                    "delta_per_user": str(payload.delta),
                    "total_admin_credit": str(total_admin_credit),
                },
            )
            conn.commit()
            return UserCreditBulkView(
                items=[
                    UserCreditView(user_id=target.user_id, username=target.username, credit=credit)
                    for target, credit in zip(targets, credits, strict=True)
                ],
                delta=payload.delta,
                total_admin_credit=total_admin_credit,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="USER credit batch could not be changed") from exc

