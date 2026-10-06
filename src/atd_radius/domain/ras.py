"""Modern domain model for an IBSng A1.24 RAS/NAS."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Mapping

class RASError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class RASPort:
    name: str
    phone: str | None = None
    type: str | None = None
    comment: str | None = None
    def __post_init__(self):
        if not self.name:
            raise RASError("port name is required")

@dataclass(frozen=True, slots=True)
class RAS:
    ras_id: int
    ip: str
    description: str
    ras_type: str
    radius_secret: str
    active: bool = True
    comment: str | None = None
    ports: Mapping[str, RASPort] = field(default_factory=dict)
    ippool_ids: tuple[int, ...] = ()
    attributes: Mapping[str, str] = field(default_factory=dict)
    type_defaults: Mapping[str, object] = field(default_factory=dict)
    defaults: Mapping[str, object] = field(default_factory=lambda: {"online_check": 1})
    def __post_init__(self):
        if self.ras_id < 0:
            raise RASError("ras_id cannot be negative")
        if not self.ip or not self.description or not self.ras_type:
            raise RASError("RAS identity fields are required")
        if len(set(self.ippool_ids)) != len(self.ippool_ids):
            raise RASError("duplicate IP pool IDs are not allowed")
    def has_port(self, name: str) -> bool:
        return name in self.ports
    def has_ippool(self, pool_id: int) -> bool:
        return pool_id in self.ippool_ids
    def has_attribute(self, name: str) -> bool:
        return name in self.attributes
    def get_attribute(self, name: str, default=None):
        if name in self.attributes:
            return self.attributes[name]
        if name in self.type_defaults:
            return self.type_defaults[name]
        return self.defaults.get(name, default)
    def all_attributes(self) -> dict[str, object]:
        merged = dict(self.defaults)
        merged.update(self.type_defaults)
        merged.update(self.attributes)
        return dict(sorted(merged.items()))
    def should_check_online(self) -> bool:
        return bool(self.get_attribute("online_check", 1))


class RASRuntimeRegistry:
    """In-memory active RAS registry assembled from the native A1.24 tables.

    The source loader reads the base RAS row first, then ras_attrs,
    ras_ports and ras_ippools (the latter by serial). Reload replaces the
    complete RAS snapshot so removed attributes/ports/pools cannot survive.
    """

    def __init__(self, repository, type_defaults: Callable[[str], Mapping[str, object]] | None = None) -> None:
        self.repository = repository
        self._type_defaults = type_defaults or (lambda _ras_type: {})
        self._ras_by_id: dict[int, RAS] = {}

    def reload(self, ras_id: int | None = None) -> tuple[RAS, ...]:
        if ras_id is None:
            records = self.repository.list()
            next_state = {record.ras_id: self._load(record) for record in records if record.active}
            self._ras_by_id = next_state
        else:
            record = self.repository.get(ras_id)
            if record is None or not record.active:
                self._ras_by_id.pop(ras_id, None)
            else:
                self._ras_by_id[ras_id] = self._load(record)
        return self.active()

    def get(self, ras_id: int) -> RAS | None:
        return self._ras_by_id.get(ras_id)

    def get_by_ip(self, ip: str) -> RAS | None:
        return next((ras for ras in self._ras_by_id.values() if ras.ip == ip), None)

    def attributes(self, ras_id: int) -> list[tuple[str, str]]:
        ras = self._ras_by_id.get(ras_id)
        return list(ras.attributes.items()) if ras is not None else []

    def active(self) -> tuple[RAS, ...]:
        return tuple(self._ras_by_id[key] for key in sorted(self._ras_by_id))

    def snapshot(self) -> Mapping[int, RAS]:
        return dict(self._ras_by_id)

    def _load(self, record) -> RAS:
        attrs = dict(self.repository.attributes(record.ras_id))
        ports = {
            port.port_name: RASPort(
                name=port.port_name,
                phone=port.phone,
                type=port.type,
                comment=port.comment,
            )
            for port in self.repository.ports(record.ras_id)
        }
        ippools = tuple(
            pool.ippool_id
            for pool in sorted(self.repository.ippools(record.ras_id), key=lambda item: item.serial)
        )
        return RAS(
            ras_id=record.ras_id,
            ip=record.ip,
            description=record.description,
            ras_type=record.ras_type,
            radius_secret=record.radius_secret,
            active=record.active,
            comment=record.comment,
            ports=ports,
            ippool_ids=ippools,
            attributes=attrs,
            type_defaults=dict(self._type_defaults(record.ras_type)),
        )
