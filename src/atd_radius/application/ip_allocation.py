"""Concurrency-safe IP allocation contract.

The repository implementation must perform the selection and state transition
inside one PostgreSQL transaction using row locks. This service deliberately
keeps allocation policy out of the RADIUS protocol adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Allocation:
    address: str
    pool_id: int


class IPAllocator(Protocol):
    def allocate(self, pool_id: int, user_id: int, session_id: str) -> Allocation | None: ...
    def release(self, address: str, session_id: str) -> None: ...


class IPAllocationService:
    def __init__(self, allocator: IPAllocator):
        self.allocator = allocator

    def assign(self, pool_id: int, user_id: int, session_id: str) -> Allocation:
        allocation = self.allocator.allocate(pool_id, user_id, session_id)
        if allocation is None:
            raise RuntimeError("no IP address available in the requested pool")
        return allocation

    def release(self, address: str, session_id: str) -> None:
        self.allocator.release(address, session_id)
