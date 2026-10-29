"""A1.24 per-user assign_ip address container semantics.

The legacy assign_ip plugin owns a separate ordered free/used list for each
user's comma-separated assign_ip attribute. This is distinct from the RAS
ippool plugin and must not be persisted in an invented allocation table.
"""
from __future__ import annotations

import threading
from collections.abc import Iterable


class AssignedIPError(ValueError):
    """Base error for a user-assigned IP pool."""


class AssignedIPConflict(AssignedIPError):
    """The requested address is not free for this user."""


class AssignedIPNotInUse(AssignedIPError):
    """The address is not currently allocated by this user's container."""


class UserAssignedIPContainer:
    """Ordered, thread-safe free/used list matching A1.24 IPPoolContainer."""

    def __init__(self, addresses: Iterable[str]) -> None:
        self._lock = threading.RLock()
        self._all = self._normalize(addresses)
        self._free = list(self._all)
        self._used: list[str] = []

    @staticmethod
    def _normalize(addresses: Iterable[str]) -> tuple[str, ...]:
        # Preserve configured order and remove duplicate entries; duplicates
        # cannot represent two independently usable leases for one IPv4 host.
        result: list[str] = []
        seen: set[str] = set()
        for raw in addresses:
            address = str(raw).strip()
            if not address:
                continue
            if address not in seen:
                result.append(address)
                seen.add(address)
        return tuple(result)

    @classmethod
    def from_attribute(cls, value: str | None) -> "UserAssignedIPContainer":
        return cls((value or "").split(","))

    @property
    def all_ips(self) -> tuple[str, ...]:
        with self._lock:
            return self._all

    @property
    def free_ips(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._free)

    @property
    def used_ips(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._used)

    def allocate(self) -> str | None:
        """Return the first free address; A1.24 treats exhaustion as no IP."""
        with self._lock:
            if not self._free:
                return None
            address = self._free.pop(0)
            self._used.append(address)
            return address

    def claim(self, address: str) -> bool:
        """Reserve a specified configured IP; return False if not in this pool."""
        with self._lock:
            if address not in self._all:
                return False
            try:
                self._free.remove(address)
            except ValueError as exc:
                raise AssignedIPConflict(
                    f"address {address} is already used by this user's pool"
                ) from exc
            self._used.append(address)
            return True

    def release(self, address: str) -> None:
        with self._lock:
            try:
                self._used.remove(address)
            except ValueError as exc:
                raise AssignedIPNotInUse(
                    f"address {address} is not used by this user's pool"
                ) from exc
            # A1.24 does not re-add an address removed from the attribute while
            # the lease was active.
            if address in self._all:
                self._free.append(address)

    def reload(self, addresses: Iterable[str]) -> None:
        """Refresh configured addresses while preserving still-valid active use."""
        with self._lock:
            new_all = self._normalize(addresses)
            retained = [address for address in self._used if address in new_all]
            retained_set = set(retained)
            self._all = new_all
            self._used = retained
            self._free = [address for address in new_all if address not in retained_set]
