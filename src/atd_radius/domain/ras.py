"""Modern domain model for an IBSng A1.24 RAS/NAS."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

PORT_TYPES = frozenset({"Internet", "Voice-Origination", "Voice-Termination"})

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
        if self.type is not None and self.type not in PORT_TYPES:
            raise RASError(f"unsupported A1.24 port type: {self.type}")

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
