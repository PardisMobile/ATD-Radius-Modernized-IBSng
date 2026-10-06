"""Session lifecycle adapter for RADIUS Accounting-Request events."""
from __future__ import annotations
from dataclasses import dataclass
from .accounting_lifecycle import AccountingEvent, AccountingStatus
from .radius_runtime import SessionKey, SessionRegistry, SessionState

@dataclass(frozen=True, slots=True)
class AccountingSessionResult:
    state: SessionState
    delta_input_octets: int = 0
    delta_output_octets: int = 0

class AccountingSessionService:
    """Apply A1.24-style Start/Interim/Stop events to the runtime registry."""
    def __init__(self, registry: SessionRegistry) -> None:
        self.registry = registry

    def apply(self, event: AccountingEvent, user_id: int, ras_id: int) -> AccountingSessionResult:
        if not event.session_id:
            raise ValueError("Acct-Session-Id is required")
        key = SessionKey(user_id, ras_id, event.session_id)
        if event.status is AccountingStatus.START:
            return AccountingSessionResult(
                self.registry.start(key, dict(event.attributes))
            )
        current = self.registry.get(key)
        if current is None:
            if event.status is AccountingStatus.INTERIM:
                state = self.registry.start(key, dict(event.attributes))
                return AccountingSessionResult(state)
            raise LookupError("RADIUS session not found")
        if event.status is AccountingStatus.INTERIM:
            di, do = self.registry.update(key, event.input_octets, event.output_octets)
            return AccountingSessionResult(current, di, do)
        if event.status is AccountingStatus.STOP:
            di, do = self.registry.update(key, event.input_octets, event.output_octets)
            state = self.registry.stop(key, event.input_octets, event.output_octets)
            return AccountingSessionResult(state, di, do)
        raise ValueError(f"unsupported accounting status: {event.status}")
