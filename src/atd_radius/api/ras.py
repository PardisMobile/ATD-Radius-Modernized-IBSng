from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.operational_audit import OperationalAuditRepository
from atd_radius.infrastructure.ras import RASRepository

router = APIRouter(prefix="/ras", tags=["RAS"])

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



class RASPayload(BaseModel):
    ras_description: str = Field(min_length=1)
    ras_ip: str = Field(min_length=1)
    ras_type: str = Field(min_length=1)
    radius_secret: str = Field(min_length=1)
    active: bool = True
    comment: str | None = None


class RASView(RASPayload):
    ras_id: int


class RASListView(BaseModel):
    ras_id: int
    ras_description: str
    ras_ip: str
    ras_type: str
    active: bool
    comment: str | None


class RASPortPayload(BaseModel):
    port_name: str = Field(min_length=1)
    phone: str | None = None
    type: str | None = None
    comment: str | None = None


class RASInfo(RASView):
    ports: list[RASPortPayload]
    attrs: list[dict[str, str]]
    ippools: list[dict[str, int]]


@router.get("", response_model=list[RASListView])
def ras_list(admin: AdminPrincipal = Depends(require_admin_permission("LIST RAS"))) -> list[RASListView]:
    with connection() as conn:
        records = RASRepository(conn).list()
    return [RASListView(ras_id=x.ras_id, ras_description=x.description, ras_ip=x.ip, ras_type=x.ras_type,
                        active=x.active, comment=x.comment) for x in records]


@router.get("/{ras_id}", response_model=RASInfo)
def ras_information(ras_id: int, admin: AdminPrincipal = Depends(require_admin_permission("GET RAS INFORMATION"))) -> RASInfo:
    with connection() as conn:
        repo = RASRepository(conn)
        record = repo.get(ras_id)
        if record is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        return RASInfo(
            ras_id=record.ras_id, ras_description=record.description, ras_ip=record.ip,
            ras_type=record.ras_type, radius_secret=record.radius_secret, active=record.active,
            comment=record.comment,
            ports=[RASPortPayload(port_name=p.port_name, phone=p.phone, type=p.type, comment=p.comment) for p in repo.ports(ras_id)],
            attrs=[{"attr_name": n, "attr_value": v} for n, v in repo.attributes(ras_id)],
            ippools=[{"serial": x.serial, "ras_id": x.ras_id, "ippool_id": x.ippool_id} for x in repo.ippools(ras_id)],
        )


@router.post("", response_model=RASView, status_code=201)
def add_new_ras(payload: RASPayload, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> RASView:
    try:
        with connection() as conn:
            repo = RASRepository(conn)
            record = repo.create(payload.ras_description, payload.ras_ip, payload.ras_type, payload.radius_secret,
                                 payload.active, payload.comment)
            _audit(conn, admin, "ras.create", "ras", str(record.ras_id))
            conn.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="RAS could not be created") from exc
    return RASView(ras_id=record.ras_id, ras_description=record.description, ras_ip=record.ip, ras_type=record.ras_type,
                   radius_secret=record.radius_secret, active=record.active, comment=record.comment)


@router.put("/{ras_id}", response_model=RASView)
def edit_ras_information(ras_id: int, payload: RASPayload, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> RASView:
    try:
        with connection() as conn:
            record = RASRepository(conn).update(ras_id, payload.ras_description, payload.ras_ip, payload.ras_type,
                                                payload.radius_secret, payload.active, payload.comment)
            _audit(conn, admin, "ras.update", "ras", str(ras_id))
            conn.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="RAS could not be updated") from exc
    return RASView(ras_id=record.ras_id, ras_description=record.description, ras_ip=record.ip, ras_type=record.ras_type,
                   radius_secret=record.radius_secret, active=record.active, comment=record.comment)


@router.delete("/{ras_id}", status_code=204)
def delete_ras(ras_id: int, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> None:
    try:
        with connection() as conn:
            RASRepository(conn).delete(ras_id)
            _audit(conn, admin, "ras.delete", "ras", str(ras_id))
            conn.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail="RAS could not be deleted") from exc


@router.get("/{ras_id}/ports", response_model=list[RASPortPayload])
def ras_ports(ras_id: int, admin: AdminPrincipal = Depends(require_admin_permission("GET RAS INFORMATION"))) -> list[RASPortPayload]:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        return [RASPortPayload(port_name=p.port_name, phone=p.phone, type=p.type, comment=p.comment) for p in repo.ports(ras_id)]


@router.put("/{ras_id}/ports/{port_name}")
def edit_ras_port(ras_id: int, port_name: str, payload: RASPortPayload, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> dict[str, bool]:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        repo.upsert_port(ras_id, payload.port_name, payload.phone, payload.type, payload.comment)
        _audit(conn, admin, "ras.port.update", "ras_port", f"{ras_id}:{payload.port_name}")
        conn.commit()
    return {"ok": True}


@router.delete("/{ras_id}/ports/{port_name}", status_code=204)
def delete_ras_port(ras_id: int, port_name: str, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> None:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        repo.delete_port(ras_id, port_name)
        _audit(conn, admin, "ras.port.delete", "ras_port", f"{ras_id}:{port_name}")
        conn.commit()


class RASAttributePayload(BaseModel):
    attr_name: str = Field(min_length=1)
    attr_value: str


@router.get("/{ras_id}/attrs")
def ras_attributes(ras_id: int, admin: AdminPrincipal = Depends(require_admin_permission("GET RAS INFORMATION"))) -> list[dict[str, str]]:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        return [{"attr_name": n, "attr_value": v} for n, v in repo.attributes(ras_id)]


@router.put("/{ras_id}/attrs/{attr_name}")
def set_ras_attribute(ras_id: int, attr_name: str, payload: RASAttributePayload, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> dict[str, bool]:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        repo.set_attribute(ras_id, attr_name, payload.attr_value)
        _audit(conn, admin, "ras.attribute.set", "ras_attribute", f"{ras_id}:{attr_name}")
        conn.commit()
    return {"ok": True}


@router.delete("/{ras_id}/attrs/{attr_name}", status_code=204)
def delete_ras_attribute(ras_id: int, attr_name: str, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> None:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        repo.delete_attribute(ras_id, attr_name)
        _audit(conn, admin, "ras.attribute.delete", "ras_attribute", f"{ras_id}:{attr_name}")
        conn.commit()


class RASIPPoolPayload(BaseModel):
    ippool_id: int = Field(gt=0)


@router.get("/{ras_id}/ippools")
def ras_ippools(ras_id: int, admin: AdminPrincipal = Depends(require_admin_permission("GET RAS INFORMATION"))) -> list[dict[str, int]]:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        return [{"serial": x.serial, "ras_id": x.ras_id, "ippool_id": x.ippool_id} for x in repo.ippools(ras_id)]


@router.post("/{ras_id}/ippools", status_code=201)
def add_ras_ippool(ras_id: int, payload: RASIPPoolPayload, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> dict[str, int]:
    try:
        with connection() as conn:
            repo = RASRepository(conn)
            if repo.get(ras_id) is None:
                raise HTTPException(status_code=404, detail="RAS not found")
            serial = repo.add_ippool(ras_id, payload.ippool_id)
            _audit(conn, admin, "ras.ippool.add", "ras_ippool", str(serial))
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="IPPool could not be assigned to RAS") from exc
    return {"serial": serial, "ras_id": ras_id, "ippool_id": payload.ippool_id}


@router.delete("/{ras_id}/ippools/{serial}", status_code=204)
def delete_ras_ippool(ras_id: int, serial: int, admin: AdminPrincipal = Depends(require_admin_permission("CHANGE RAS"))) -> None:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        repo.delete_ippool(serial)
        _audit(conn, admin, "ras.ippool.delete", "ras_ippool", str(serial))
        conn.commit()
