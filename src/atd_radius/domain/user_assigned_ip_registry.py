"""Process-local coordinator for A1.24 per-user assign_ip leases."""
from __future__ import annotations
import threading
from collections.abc import Iterable
from .user_assigned_ip import AssignedIPConflict, AssignedIPNotInUse, UserAssignedIPContainer


class UserAssignedIPRegistry:
    """Manage ordered user address pools and the pending-to-session handoff."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._containers: dict[int, UserAssignedIPContainer] = {}
        self._pending: dict[str, tuple[int, str]] = {}
        self._sessions: dict[tuple[int, int, str], str] = {}

    @staticmethod
    def _addresses(value: str | Iterable[str] | None) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(value.split(",")) if isinstance(value, str) else tuple(map(str, value))

    def _pool(self, user_id: int, configured: str | Iterable[str] | None):
        user_id = int(user_id)
        addresses = self._addresses(configured)
        pool = self._containers.get(user_id)
        if pool is None:
            pool = self._containers[user_id] = UserAssignedIPContainer(addresses)
        else:
            pool.reload(addresses)
        return pool

    def allocate(self, user_id: int, configured: str | Iterable[str] | None) -> str | None:
        with self._lock:
            return self._pool(user_id, configured).allocate()

    def claim(self, user_id: int, configured: str | Iterable[str] | None, address: str) -> bool:
        with self._lock:
            return self._pool(user_id, configured).claim(str(address))

    def reserve(self, user_id: int, configured: str | Iterable[str] | None, request_key: str) -> str | None:
        """Reserve once per Access-Request identity; retransmits get same IP."""
        if not request_key:
            raise ValueError("request_key is required")
        user_id = int(user_id)
        with self._lock:
            existing = self._pending.get(request_key)
            if existing is not None:
                if existing[0] != user_id:
                    raise AssignedIPConflict("request key belongs to another user")
                return existing[1]
            address = self._pool(user_id, configured).allocate()
            if address is not None:
                self._pending[request_key] = (user_id, address)
            return address

    def reserve_specific(
        self, user_id: int, configured: str | Iterable[str] | None,
        request_key: str, address: str,
    ) -> str | None:
        """Reserve a configured address for re-online; same request is idempotent.

        Returns None when the requested address is not in the user's configured
        pool. A used address raises AssignedIPConflict, matching A1.24's
        remote-IP conflict behavior instead of silently allocating another IP.
        """
        if not request_key:
            raise ValueError("request_key is required")
        user_id, address = int(user_id), str(address).strip()
        with self._lock:
            existing = self._pending.get(request_key)
            if existing is not None:
                if existing != (user_id, address):
                    raise AssignedIPConflict("request key is already reserved differently")
                return address
            pool = self._pool(user_id, configured)
            if not pool.claim(address):
                return None
            self._pending[request_key] = (user_id, address)
            return address

    def bind_session(
        self, user_id: int, ras_id: int, session_id: str, address: str,
        configured: str | Iterable[str] | None,
    ) -> str:
        """Claim an address for a known session, idempotently.

        This is the Accounting/recovery path for sessions without a pending
        Access reservation. A session key cannot be rebound to another IP.
        """
        if not session_id:
            raise ValueError("session_id is required")
        user_id, ras_id, session_id, address = (
            int(user_id), int(ras_id), str(session_id), str(address).strip()
        )
        key = (user_id, ras_id, session_id)
        with self._lock:
            prior = self._sessions.get(key)
            if prior is not None:
                if prior != address:
                    raise AssignedIPConflict("session owns a different address")
                return prior
            pool = self._pool(user_id, configured)
            if not pool.claim(address):
                raise AssignedIPConflict("address is not configured for this user")
            self._sessions[key] = address
            return address

    def consume(self, request_key: str, ras_id: int, session_id: str) -> str | None:
        """Bind a pending reservation to its accepted Accounting session."""
        if not request_key or not session_id:
            return None
        with self._lock:
            pending = self._pending.pop(request_key, None)
            if pending is None:
                return None
            user_id, address = pending
            key = (user_id, int(ras_id), str(session_id))
            prior = self._sessions.get(key)
            if prior is not None and prior != address:
                # Restore pending ownership rather than leaking the reserved IP.
                self._pending[request_key] = pending
                raise AssignedIPConflict("session owns a different address")
            self._sessions[key] = address
            return address

    def release_request(self, request_key: str) -> bool:
        """Release only the pending reservation for a rejected login."""
        with self._lock:
            pending = self._pending.pop(request_key, None)
            if pending is None:
                return False
            pool = self._containers.get(pending[0])
            if pool is not None:
                pool.release(pending[1])
            return True

    def release_session(self, user_id: int, ras_id: int, session_id: str) -> str | None:
        """Release the lease for exactly one session; duplicate Stop is harmless."""
        with self._lock:
            key = (int(user_id), int(ras_id), str(session_id))
            address = self._sessions.pop(key, None)
            if address is None:
                return None
            pool = self._containers.get(int(user_id))
            if pool is not None:
                try:
                    pool.release(address)
                except AssignedIPNotInUse:
                    # A config reload can remove an address while it is active.
                    pass
            return address

    def pending(self, request_key: str) -> tuple[int, str] | None:
        with self._lock:
            return self._pending.get(request_key)

    def session_address(self, user_id: int, ras_id: int, session_id: str) -> str | None:
        with self._lock:
            return self._sessions.get((int(user_id), int(ras_id), str(session_id)))

    def snapshot(self, user_id: int):
        """Return (all, free, used) address tuples for tests/diagnostics."""
        with self._lock:
            pool = self._containers.get(int(user_id))
            return ((), (), ()) if pool is None else (pool.all_ips, pool.free_ips, pool.used_ips)
