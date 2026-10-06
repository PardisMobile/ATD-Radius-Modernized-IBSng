"""Native A1.24 IP allocation application boundary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class Allocation:
    address: str
    pool_id: int

class IPAllocator(Protocol):
    def allocate(self, pool_id: int) -> str: ...
    def release(self, pool_id: int, address: str) -> None: ...

class IPAllocationService:
    """Application facade over the native process-local A1.24 pool runtime."""
    def __init__(self, allocator: IPAllocator):
        self.allocator = allocator

    def assign(self, pool_id: int) -> Allocation:
        return Allocation(address=self.allocator.allocate(pool_id), pool_id=pool_id)

    def release(self, pool_id: int, address: str) -> None:
        self.allocator.release(pool_id, address)
