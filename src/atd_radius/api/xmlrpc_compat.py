"""A1.24-compatible XML-RPC transport for the registered IAS handler methods."""
from __future__ import annotations

import xmlrpc.client

from fastapi import APIRouter, Request, Response

from atd_radius.application.admin_authentication import AdminAuthenticator
from atd_radius.infrastructure.admin_repository import AdminRepository
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.ias_events_repository import PostgresIASEventRepository
from atd_radius.infrastructure.ias_user_info import PostgresIASUserInfoRepository
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository

router = APIRouter()
_REGISTERED_METHODS = {"ias.getEvents", "ias.deleteEvents", "ias.getIASUserInfo"}
_MAX_BODY_BYTES = 1024 * 1024


def _as_int(value, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _fix_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        try:
            return [value[str(index)] if str(index) in value else value[index]
                    for index in range(len(value))]
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid XML-RPC list encoding") from exc
    raise ValueError("expected an XML-RPC list")


def _execute_ias_method(method: str, params, remote_addr: str | None):
    if method not in _REGISTERED_METHODS:
        raise ValueError(f"IAS handler has no registered method: {method}")
    if len(params) != 1 or not isinstance(params[0], dict):
        raise ValueError("IAS requests require one parameter dictionary")
    args = dict(params[0])
    auth_type = args.pop("auth_type", None)
    auth_name = args.pop("auth_name", None)
    auth_pass = args.pop("auth_pass", None)
    if auth_type != "ADMIN" or not isinstance(auth_name, str) or not isinstance(auth_pass, str):
        raise PermissionError("IAS methods require ADMIN authentication")

    with connection() as conn:
        admin = AdminAuthenticator(AdminRepository(conn)).authenticate(
            auth_name, auth_pass, remote_addr or ""
        )
        # A1.24 registers no HANDLE_IAS_EVENTS permission class. Its canDo
        # check therefore denies non-GOD admins; only the native GOD bypass
        # reaches these three registered IAS methods.
        if not AdminRepository(conn).permissions(admin.admin_id).is_god():
            raise PermissionError("Access denied")

        if method == "ias.getEvents":
            required = {"from_event_id", "from", "to"}
            if not required.issubset(args):
                raise ValueError("missing IAS event range arguments")
            events = PostgresIASEventRepository(conn).list_events(
                _as_int(args["from_event_id"], "from_event_id"),
                _as_int(args["from"], "from"),
                _as_int(args["to"], "to"),
            )
            return [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "event_date": event.event_date,
                    "actor": event.actor,
                    "amount": float(event.amount) if event.amount is not None else 0.0,
                    "destinations": event.destinations,
                    "comment": event.comment,
                }
                for event in events
            ]

        if method == "ias.deleteEvents":
            if "event_ids" not in args:
                raise ValueError("missing event_ids")
            event_ids = [_as_int(value, "event_id") for value in _fix_list(args["event_ids"])]
            deleted = PostgresIASEventRepository(conn).delete_events(event_ids)
            OperationalAuditRepository(conn).append(
                actor_admin_id=admin.admin_id,
                actor_username=admin.username,
                action="ias.events.delete",
                outcome="success",
                target_type="ias_event",
                target_id=",".join(str(value) for value in event_ids),
                remote_addr=remote_addr,
                details={"requested_count": len(event_ids), "deleted_count": deleted, "transport": "xmlrpc"},
            )
            conn.commit()
            return ""

        if "user_ids" not in args:
            raise ValueError("missing user_ids")
        user_ids = [_as_int(value, "user_id") for value in _fix_list(args["user_ids"])]
        users = PostgresIASUserInfoRepository(conn).get_many(user_ids)
        result = []
        for user in users:
            item = {
                "user_id": str(user.user_id),
                "owner": user.owner,
                "credit": float(user.credit),
            }
            if user.normal_username is not None:
                item["normal_username"] = user.normal_username
            if user.voip_username is not None:
                item["voip_username"] = user.voip_username
            result.append(item)
        return result


@router.post("/xmlrpc")
async def xmlrpc_compatibility_endpoint(request: Request) -> Response:
    body = await request.body()
    if len(body) > _MAX_BODY_BYTES:
        fault = xmlrpc.client.Fault(1, "XML-RPC request is too large")
        return Response(
            content=xmlrpc.client.dumps(fault, encoding="utf-8"),
            media_type="text/xml",
            status_code=200,
        )
    try:
        params, method = xmlrpc.client.loads(body, use_builtin_types=True)
        result = _execute_ias_method(method, params, request.client.host if request.client else None)
        payload = xmlrpc.client.dumps((result,), methodresponse=True, allow_none=False, encoding="utf-8")
    except Exception as exc:
        payload = xmlrpc.client.dumps(xmlrpc.client.Fault(1, str(exc)), encoding="utf-8")
    return Response(content=payload, media_type="text/xml", status_code=200)
