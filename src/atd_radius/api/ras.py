from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.ras import RASRepository

router = APIRouter(prefix="/ras", tags=["RAS"])


class RASPayload(BaseModel):
    ras_description: str = Field(min_length=1)
    ras_ip: str = Field(min_length=1)
    ras_type: str = Field(min_length=1)
    radius_secret: str = Field(min_length=1)
    active: bool = True
    comment: str | None = None


class RASView(RASPayload):
    ras_id: int


class RASPortPayload(BaseModel):
    port_name: str = Field(min_length=1)
    phone: str | None = None
    type: str | None = None
    comment: str | None = None


class RASInfo(RASView):
    ports: list[RASPortPayload]
    attrs: list[dict[str, str]]
    ippools: list[dict[str, int]]


@router.get("", response_model=list[RASView])
def ras_list() -> list[RASView]:
    with connection() as conn:
        records = RASRepository(conn).list()
    return [RASView(ras_id=x.ras_id, ras_description=x.description, ras_ip=x.ip, ras_type=x.ras_type,
                    radius_secret=x.radius_secret, active=x.active, comment=x.comment) for x in records]


@router.get("/{ras_id}", response_model=RASInfo)
def ras_information(ras_id: int) -> RASInfo:
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
def add_new_ras(payload: RASPayload) -> RASView:
    try:
        with connection() as conn:
            repo = RASRepository(conn)
            record = repo.create(payload.ras_description, payload.ras_ip, payload.ras_type, payload.radius_secret,
                                 payload.active, payload.comment)
            conn.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="RAS could not be created") from exc
    return RASView(ras_id=record.ras_id, ras_description=record.description, ras_ip=record.ip, ras_type=record.ras_type,
                   radius_secret=record.radius_secret, active=record.active, comment=record.comment)


@router.put("/{ras_id}", response_model=RASView)
def edit_ras_information(ras_id: int, payload: RASPayload) -> RASView:
    try:
        with connection() as conn:
            record = RASRepository(conn).update(ras_id, payload.ras_description, payload.ras_ip, payload.ras_type,
                                                payload.radius_secret, payload.active, payload.comment)
            conn.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="RAS could not be updated") from exc
    return RASView(ras_id=record.ras_id, ras_description=record.description, ras_ip=record.ip, ras_type=record.ras_type,
                   radius_secret=record.radius_secret, active=record.active, comment=record.comment)


@router.delete("/{ras_id}", status_code=204)
def delete_ras(ras_id: int) -> None:
    try:
        with connection() as conn:
            RASRepository(conn).delete(ras_id)
            conn.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail="RAS could not be deleted") from exc


@router.get("/{ras_id}/ports", response_model=list[RASPortPayload])
def ras_ports(ras_id: int) -> list[RASPortPayload]:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        return [RASPortPayload(port_name=p.port_name, phone=p.phone, type=p.type, comment=p.comment) for p in repo.ports(ras_id)]


@router.put("/{ras_id}/ports/{port_name}")
def edit_ras_port(ras_id: int, port_name: str, payload: RASPortPayload) -> dict[str, bool]:
    with connection() as conn:
        repo = RASRepository(conn)
        if repo.get(ras_id) is None:
            raise HTTPException(status_code=404, detail="RAS not found")
        repo.upsert_port(ras_id, port_name, payload.phone, payload.type, payload.comment)
        conn.commit()
    return {"ok": True}
