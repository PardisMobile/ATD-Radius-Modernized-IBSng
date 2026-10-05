"""Repository boundary for IBSng-compatible scoped attributes.

The repository intentionally stores arbitrary attribute names/values instead of
turning the A1.24 attribute system into a fixed column model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredAttribute:
    owner_type: str
    owner_id: int
    name: str
    value: str
    position: int = 0


class AttributeRepository(Protocol):
    def list_for_owner(self, owner_type: str, owner_id: int) -> list[StoredAttribute]: ...

    def replace_for_owner(self, owner_type: str, owner_id: int, attributes: list[StoredAttribute]) -> None: ...


class InMemoryAttributeRepository:
    """Reference implementation used by unit/compatibility tests."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, int], list[StoredAttribute]] = {}

    def list_for_owner(self, owner_type: str, owner_id: int) -> list[StoredAttribute]:
        return list(self._items.get((owner_type, owner_id), ()))

    def replace_for_owner(self, owner_type: str, owner_id: int, attributes: list[StoredAttribute]) -> None:
        self._items[(owner_type, owner_id)] = list(attributes)
