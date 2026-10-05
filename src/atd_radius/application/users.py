from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from atd_radius.domain.models import User, UserKind


class UserStore(Protocol):
    def create(self, username: str, status: str = "active") -> object: ...
    def find_by_username(self, username: str) -> User | None: ...


@dataclass(slots=True)
class UserService:
    """Application use cases for user lifecycle operations."""

    repository: UserStore

    def create(self, username: str) -> User:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        record = self.repository.create(username, "active")
        return User(id=record.id, username=record.username, kind=UserKind.NORMAL, enabled=True)

    def get(self, username: str) -> User | None:
        return self.repository.find_by_username(username.strip())
