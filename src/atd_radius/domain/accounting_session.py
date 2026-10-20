"""Session lifecycle adapter for RADIUS Accounting-Request events."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .accounting_lifecycle import AccountingEvent, AccountingStatus
from .radius_runtime import SessionKey, SessionRegistry, SessionState


class AccountingPersistence(Protocol):
    def start(self, event: AccountingEvent, user_id: int, ras_id: int) -> int | None: ...
    def update(self, connection_log_id: int, event: AccountingEvent) -> None: ...
    def stop(self, connection_log_id: int, event: AccountingEvent, credit_used=None) -> None: ...


@dataclass(frozen=True, slots=True)
class AccountingSessionResult:
    state: SessionState
    delta_input_octets: int = 0
    delta_output_octets: int = 0
    connection_log_id: int | None = None
    credit_used: str | None = None
    created: bool = False


class ChargeSettlement(Protocol):
    def start(self, state: SessionState, when, ras_id: int, port: str | None) -> None: ...
    def update(self, state: SessionState, when, ras_id: int, port: str | None): ...
    def settle(self, state: SessionState, when, ras_id: int, port: str | None): ...


class AccountingSessionService:
    def __init__(
        self, registry: SessionRegistry, persistence: AccountingPersistence | None = None,
        charge: ChargeSettlement | None = None, state_store=None,
    ):
        self.registry = registry
        self.persistence = persistence
        self.charge = charge
        self.state_store = state_store

    def persist_state(self, state: SessionState) -> None:
        """Persist state inside the same caller-owned transaction as accounting."""
        if self.state_store is not None:
            self.state_store.save(state)

    def refresh_user_sessions(self, user_id: int) -> None:
        """Refresh a user's sessions from shared storage before MultiLogin admission."""
        store = self.state_store
        list_active = getattr(store, "list_active", None)
        lock = getattr(store, "lock", None)
        load = getattr(store, "get", None)
        if not (callable(list_active) and callable(lock) and callable(load)):
            return
        durable = [state for state in list_active() if state.key.user_id == user_id]
        local = self.registry.all_for_user(user_id)
        keys = {state.key for state in durable}
        keys.update(state.key for state in local)
        for key in sorted(keys, key=lambda item: (item.user_id, item.ras_id, item.unique_id)):
            lock(key)
            state = load(key)
            if state is None:
                self.registry.remove(key)
            else:
                self.registry.replace(state)

    def refresh_ras_sessions(self, ras_id: int) -> None:
        """Refresh every session on one RAS under per-session DB locks.

        Control requests are rare, so reconciling this RAS scope is preferable
        to applying Disconnect/CoA against a potentially stale worker-local view.
        """
        store = self.state_store
        list_active = getattr(store, "list_active", None)
        lock = getattr(store, "lock", None)
        load = getattr(store, "get", None)
        if not (callable(list_active) and callable(lock) and callable(load)):
            return
        durable = [state for state in list_active() if state.key.ras_id == ras_id]
        local = self.registry.all_for_ras(ras_id)
        keys = {state.key for state in durable}
        keys.update(state.key for state in local)
        for key in sorted(keys, key=lambda item: (item.user_id, item.ras_id, item.unique_id)):
            lock(key)
            state = load(key)
            if state is None:
                self.registry.remove(key)
            else:
                self.registry.replace(state)

    def apply(self, event, user_id, ras_id) -> AccountingSessionResult:
        # In-process atomicity remains useful; durable snapshots are written before
        # the caller commits the same PostgreSQL transaction.
        with self.registry.synchronized():
            key = SessionKey(user_id, ras_id, event.session_id) if event.session_id else None
            lock = getattr(self.state_store, "lock", None)
            load = getattr(self.state_store, "get", None)
            if key is not None and callable(lock) and callable(load):
                # PostgreSQL transaction advisory lock serializes the same native
                # session across workers; refresh the local copy only after lock.
                lock(key)
                persisted = load(key)
                if persisted is None:
                    self.registry.remove(key)
                else:
                    self.registry.replace(persisted)
            return self._apply_locked(event, user_id, ras_id)

    def _apply_locked(self, event, user_id, ras_id) -> AccountingSessionResult:
        if not event.session_id:
            raise ValueError("Acct-Session-Id is required")
        key = SessionKey(user_id, ras_id, event.session_id)
        current = self.registry.get(key)

        if event.status is AccountingStatus.START and current is None:
            state = self.registry.start(
                key, dict(event.attributes), event.input_octets, event.output_octets,
                event.observed_at, ras_multi_login_allowed=event.ras_multi_login_allowed,
            )
            port = event.attributes.get("NAS-Port") or event.attributes.get("NAS-Port-Id")
            if self.charge:
                self.charge.start(state, event.observed_at, ras_id, port)
            log_id = (
                self.persistence.start(event, user_id, ras_id)
                if self.persistence and "no_connection_log" not in event.attributes else None
            )
            if log_id is not None:
                state.attributes = {**state.attributes, "__connection_log_id": str(log_id)}
            self.persist_state(state)
            return AccountingSessionResult(state, connection_log_id=log_id, created=True)

        if current is not None and current.stopped:
            return AccountingSessionResult(
                current,
                connection_log_id=int(current.attributes["__connection_log_id"])
                if "__connection_log_id" in current.attributes else None,
            )
        if current is not None and event.status is AccountingStatus.START:
            return AccountingSessionResult(
                current,
                connection_log_id=int(current.attributes["__connection_log_id"])
                if "__connection_log_id" in current.attributes else None,
            )

        if current is None:
            if event.status is AccountingStatus.INTERIM:
                state = self.registry.start(
                    key, dict(event.attributes), event.input_octets, event.output_octets,
                    event.observed_at, ras_multi_login_allowed=event.ras_multi_login_allowed,
                )
                port = event.attributes.get("NAS-Port") or event.attributes.get("NAS-Port-Id")
                if self.charge:
                    self.charge.start(state, event.observed_at, ras_id, port)
                log_id = (
                    self.persistence.start(event, user_id, ras_id)
                    if self.persistence and "no_connection_log" not in event.attributes else None
                )
                if log_id is not None:
                    state.attributes = {**state.attributes, "__connection_log_id": str(log_id)}
                self.persist_state(state)
                return AccountingSessionResult(state, connection_log_id=log_id, created=True)
            raise LookupError("RADIUS session not found")

        log_id = (
            int(current.attributes["__connection_log_id"])
            if "__connection_log_id" in current.attributes else None
        )
        port = (
            event.attributes.get("NAS-Port") or event.attributes.get("NAS-Port-Id")
            or current.attributes.get("NAS-Port") or current.attributes.get("NAS-Port-Id")
        )
        current.attributes = {**current.attributes, **event.attributes}

        if event.status in (AccountingStatus.INTERIM, AccountingStatus.ALIVE):
            delta_in, delta_out = self.registry.update(key, event.input_octets, event.output_octets)
            if self.charge:
                self.charge.update(current, event.observed_at, ras_id, port)
            if self.persistence and log_id is not None:
                self.persistence.update(log_id, event)
            self.persist_state(current)
            return AccountingSessionResult(current, delta_in, delta_out, log_id)

        if event.status is AccountingStatus.STOP:
            delta_in, delta_out = self.registry.update(key, event.input_octets, event.output_octets)
            state = self.registry.stop(key, event.input_octets, event.output_octets)
            used = (
                Decimal("0") if "no_commit" in event.attributes
                else self.charge.settle(state, event.observed_at, ras_id, port)
            ) if self.charge else None
            if self.persistence and log_id is not None:
                if "no_connection_log" in event.attributes:
                    discard = getattr(self.persistence, "discard", None)
                    if discard is not None:
                        discard(log_id)
                else:
                    self.persistence.stop(log_id, event, used)
            self.persist_state(state)
            return AccountingSessionResult(
                state, delta_in, delta_out, log_id, str(used) if used is not None else None,
            )
        raise ValueError(f"unsupported accounting status: {event.status}")
