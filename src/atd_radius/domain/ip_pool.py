"""Deterministic IPv4 allocation primitives for IBSng-compatible IP pools."""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Iterable


class IPPoolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IPPool:
    name: str
    network: ipaddress.IPv4Network
    enabled: bool = True

    @classmethod
    def from_cidr(cls, name: str, cidr: str, enabled: bool = True) -> "IPPool":
        network = ipaddress.ip_network(cidr, strict=True)
        if not isinstance(network, ipaddress.IPv4Network):
            raise IPPoolError("ATD IP pools currently support IPv4 only")
        return cls(name=name, network=network, enabled=enabled)

    def addresses(self) -> Iterable[ipaddress.IPv4Address]:
        if not self.enabled:
            return ()
        return self.network.hosts()


class IPAllocator:
    """Allocate an address without ever returning an already-used address."""

    def __init__(self, pool: IPPool):
        self.pool = pool

    def allocate(self, used: Iterable[str | ipaddress.IPv4Address]) -> ipaddress.IPv4Address:
        if not self.pool.enabled:
            raise IPPoolError(f"IP pool {self.pool.name!r} is disabled")
        used_set = {ipaddress.ip_address(value) for value in used}
        for address in self.pool.addresses():
            if address not in used_set:
                return address
        raise IPPoolError(f"IP pool {self.pool.name!r} is exhausted")

    def is_available(self, address: str | ipaddress.IPv4Address, used: Iterable[str | ipaddress.IPv4Address]) -> bool:
        candidate = ipaddress.ip_address(address)
        if candidate.version != 4 or candidate not in self.pool.network:
            return False
        return candidate not in {ipaddress.ip_address(value) for value in used}
