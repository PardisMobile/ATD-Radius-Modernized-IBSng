from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class User:
    id: UUID | None
    username: str
    enabled: bool = True
    credit: Decimal = Decimal("0")
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Group:
    id: UUID | None
    name: str
    enabled: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Service:
    id: UUID | None
    name: str
    enabled: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Ras:
    id: UUID | None
    name: str
    host: str
    secret: str
    enabled: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IpPool:
    id: UUID | None
    name: str
    network_cidr: str
    enabled: bool = True


@dataclass(slots=True)
class Session:
    id: UUID | None
    username: str
    ras_id: UUID
    started_at: datetime
    interim_at: datetime | None = None
    stopped_at: datetime | None = None
    framed_ip: str | None = None
    input_octets: int = 0
    output_octets: int = 0
    terminate_cause: str | None = None
