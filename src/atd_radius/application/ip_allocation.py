"""Concurrency-safe IP allocation application boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Allocation:
    address: str
    pool_id: UUID
    user_id: UUID | None


class IPAllocator(Protocol):
    def allocate(self, pool_id: UUID, user_id: UUID | None = None) -> Allocation | None: ...
    def release(self, pool_id: UUID, address: str) -> None: ...


class IPAllocationService:
    def __init__(self, allocator: IPAllocator):
        self.allocator = allocator

    def assign(self, pool_id: UUID, user_id: UUID | None = None) -> Allocation:
        allocation = self.allocator.allocate(pool_id, user_id)
        if allocation is None:
            raise RuntimeError("no IP address available in the requested pool")
        return Allocation(
            address=allocation.address,
            pool_id=allocation.pool_id,
            user_id=allocation.user_id,
        )

    def release(self, pool_id: UUID, address: str) -> None:
        self.allocator.release(pool_id, address)
