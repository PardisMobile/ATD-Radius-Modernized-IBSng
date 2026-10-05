"""Modern domain model derived from IBSng A1.24 behavior.

The models deliberately avoid coupling the domain to PostgreSQL, HTTP, RADIUS,
or the web UI. Protocol and persistence adapters translate into these objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class UserKind(str, Enum):
    NORMAL = "normal"
    VOIP = "voip"
    PERSISTENT_LAN = "persistent_lan"


class SessionState(str, Enum):
    STARTING = "starting"
    ONLINE = "online"
    STOPPED = "stopped"


@dataclass(slots=True)
class User:
    id: int | None
    username: str
    password_hash: str | None = None
    kind: UserKind = UserKind.NORMAL
    enabled: bool = True
    credit: Decimal = Decimal("0")
    attributes: dict[str, Any] = field(default_factory=dict)
    group_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class Group:
    id: int | None
    name: str
    description: str = ""
    enabled: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Service:
    id: int | None
    name: str
    description: str = ""
    enabled: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Ras:
    id: int | None
    name: str
    kind: str
    address: str | None = None
    secret: str | None = None
    enabled: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IPPool:
    id: int | None
    name: str
    network_cidr: str
    enabled: bool = True


@dataclass(slots=True)
class Session:
    id: int | None
    user_id: int
    ras_id: int
    unique_id: str
    state: SessionState = SessionState.STARTING
    framed_ip: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    input_octets: int = 0
    output_octets: int = 0
    terminate_cause: str | None = None


@dataclass(slots=True)
class AccountingEvent:
    session_unique_id: str
    event_type: str
    occurred_at: datetime
    input_octets: int = 0
    output_octets: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AttributeSet:
    """Effective attributes after IBSng-style inheritance."""

    values: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)
