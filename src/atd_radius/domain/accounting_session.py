"""Session lifecycle adapter for RADIUS Accounting-Request events."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .accounting_lifecycle import AccountingEvent, AccountingStatus
from .radius_runtime import SessionKey, SessionRegistry, SessionState


class AccountingPersistence(Protocol):
    def start(self, event: AccountingEvent, user_id: int, ras_id: int) -> int: ...
    def update(self, connection_log_id: int, event: AccountingEvent) -> None: ...
    def stop(self, connection_log_id: int, event: AccountingEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class AccountingSessionResult:
    state: SessionState
    delta_input_octets: int = 0
    delta_output_octets: int = 0
    connection_log_id: int | None = None


class AccountingSessionService:
    """Apply A1.24-style accounting lifecycle to runtime and optional persistence."""

    def __init__(
        self,
        registry: SessionRegistry,
        persistence: AccountingPersistence | None = None,
    ) -> None:
        self.registry = registry
        self.persistence = persistence

    def apply(self, event: AccountingEvent, user_id: int, ras_id: int) -> AccountingSessionResult:
        if not event.session_id:
            raise ValueError("Acct-Session-Id is required")
        key = SessionKey(user_id, ras_id, event.session_id)

        if event.status is AccountingStatus.START:
            state = self.registry.start(key, dict(event.attributes))
            log_id = self.persistence.start(event, user_id, ras_id) if self.persistence else None
            if log_id is not None:
                state.attributes = {**state.attributes, "__connection_log_id": str(log_id)}
            return AccountingSessionResult(state, connection_log_id=log_id)

        current = self.registry.get(key)
        if current is None:
            if event.status is AccountingStatus.INTERIM:
                state = self.registry.start(key, dict(event.attributes))
                log_id = self.persistence.start(event, user_id, ras_id) if self.persistence else None
                if log_id is not None:
                    state.attributes = {**state.attributes, "__connection_log_id": str(log_id)}
                return AccountingSessionResult(state, connection_log_id=log_id)
            raise LookupError("RADIUS session not found")

        log_id = int(current.attributes["__connection_log_id"]) if "__connection_log_id" in current.attributes else None
        if event.status is AccountingStatus.INTERIM:
            di, do = self.registry.update(key, event.input_octets, event.output_octets)
            if self.persistence and log_id is not None:
                self.persistence.update(log_id, event)
            return AccountingSessionResult(current, di, do, log_id)

        if event.status is AccountingStatus.STOP:
            di, do = self.registry.update(key, event.input_octets, event.output_octets)
            state = self.registry.stop(key, event.input_octets, event.output_octets)
            if self.persistence and log_id is not None:
                self.persistence.stop(log_id, event)
            return AccountingSessionResult(state, di, do, log_id)

        raise ValueError(f"unsupported accounting status: {event.status}")
