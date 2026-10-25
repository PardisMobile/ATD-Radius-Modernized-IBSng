"""Application adapter for A1.24 periodic-accounting hook lifecycles.

The coordinator is deliberately persistence-agnostic: a repository adapter loads
and saves native user attributes, while the caller supplies authoritative
per-session counters and a callback that requests RAS termination.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from atd_radius.domain.periodic_accounting import (
    PeriodicAccountingState,
    PeriodicQuotaConfig,
    PeriodicQuotaKind,
)


@dataclass(frozen=True, slots=True)
class PeriodicQuotaDecision:
    allowed: bool
    exhausted_keys: tuple[str, ...] = ()
    remaining_seconds: float | None = None
    next_reset: float | None = None


class PeriodicAccountingAttributes(Protocol):
    def load(self, user_id: int) -> Mapping[str, str]: ...
    def save(self, user_id: int, values: Mapping[str, str]) -> None: ...


@dataclass(slots=True)
class _UserState:
    quotas: dict[str, PeriodicAccountingState]


class PeriodicAccountingCoordinator:
    """Coordinate login/update/logout/canStayOnline for all four A1.24 quotas.

    State is keyed by native user ID and RAS instance ID. The caller must
    persist mutations transactionally with its native user-attribute adapter.
    This class does not pretend a process-local cache is durable.
    """

    DEFINITIONS = (
        ("time_periodic_accounting_daily", "daily", PeriodicQuotaKind.TIME),
        ("time_periodic_accounting_monthly", "monthly", PeriodicQuotaKind.TIME),
        ("traffic_periodic_accounting_daily", "daily", PeriodicQuotaKind.TRAFFIC),
        ("traffic_periodic_accounting_monthly", "monthly", PeriodicQuotaKind.TRAFFIC),
    )

    def __init__(
        self,
        attributes: PeriodicAccountingAttributes,
        *,
        clock: Callable[[], float],
        traffic_counters: Callable[[int, int | str], int] | None = None,
        request_termination: Callable[[int, str], None] | None = None,
        is_normal_user: Callable[[int], bool] | None = None,
    ) -> None:
        self.attributes = attributes
        self.clock = clock
        self.traffic_counters = traffic_counters or (lambda user_id, instance: 0)
        self.request_termination = request_termination or (lambda user_id, key: None)
        self.is_normal_user = is_normal_user or (lambda user_id: True)
        self._users: dict[int, _UserState] = {}

    @staticmethod
    def _number(attrs: Mapping[str, str], key: str, default: float = 0) -> float:
        try:
            return float(attrs.get(key, default))
        except (TypeError, ValueError):
            return default

    def _load_user(self, user_id: int) -> _UserState:
        if user_id in self._users:
            return self._users[user_id]
        attrs = self.attributes.load(user_id)
        quotas: dict[str, PeriodicAccountingState] = {}
        for key, period, kind in self.DEFINITIONS:
            limit_raw = attrs.get(f"{key}_limit")
            value = attrs.get(key)
            if limit_raw in (None, "") or value in (None, ""):
                continue
            try:
                limit = int(limit_raw)
                accumulated = int(self._number(attrs, f"{key}_usage"))
                reset_raw = attrs.get(f"{key}_reset")
                reset = float(reset_raw) if reset_raw not in (None, "") else None
                config = PeriodicQuotaConfig(
                    key=key, period=period, kind=kind, value=str(value),
                    limit=limit, next_reset=reset, accumulated_usage=accumulated,
                )
            except (ValueError, TypeError, OverflowError):
                # Invalid native quota configuration is not silently enforced
                # as a zero/default quota. Omit it and leave an operator-visible
                # validation path to the caller.
                continue
            quotas[key] = PeriodicAccountingState(config)
        user = _UserState(quotas)
        self._users[user_id] = user
        return user

    def _persist(self, user_id: int, user: _UserState) -> None:
        values: dict[str, str] = {}
        for key, state in user.quotas.items():
            values[f"{key}_usage"] = str(state.committed_usage + state.initial_usage)
            values[f"{key}_reset"] = str(state.next_reset or 0)
        if values:
            self.attributes.save(user_id, values)

    def login(
        self, user_id: int, instance: int | str, *, start_accounting: bool = False
    ) -> PeriodicQuotaDecision:
        now = self.clock()
        user = self._load_user(user_id)
        exhausted: list[str] = []
        counters = {
            active_instance: self.traffic_counters(user_id, active_instance)
            for state in user.quotas.values()
            if state.kind is PeriodicQuotaKind.TRAFFIC
            for active_instance in state.starts
        }
        counters[instance] = self.traffic_counters(user_id, instance)
        for key, state in user.quotas.items():
            traffic = counters[instance] if state.kind is PeriodicQuotaKind.TRAFFIC else 0
            if state.login(instance, now, traffic, counters, start_accounting=start_accounting):
                exhausted.append(key)
        self._persist(user_id, user)
        return PeriodicQuotaDecision(not exhausted, tuple(exhausted))

    def update(self, user_id: int, instance: int | str, *, start_accounting: bool = False) -> PeriodicQuotaDecision:
        now = self.clock()
        user = self._load_user(user_id)
        counters = {
            active_instance: self.traffic_counters(user_id, active_instance)
            for state in user.quotas.values()
            if state.kind is PeriodicQuotaKind.TRAFFIC
            for active_instance in state.starts
        }
        if start_accounting:
            for state in user.quotas.values():
                state.update_baseline(instance, now, counters.get(instance, 0))
        self._persist(user_id, user)
        return self.can_stay_online(user_id, instance, counters=counters)

    def logout(self, user_id: int, instance: int | str) -> Mapping[str, int | float]:
        now = self.clock()
        user = self._load_user(user_id)
        committed: dict[str, int | float] = {}
        for key, state in user.quotas.items():
            traffic = self.traffic_counters(user_id, instance) if state.kind is PeriodicQuotaKind.TRAFFIC else 0
            committed[key] = state.logout(instance, now, traffic)
        self._persist(user_id, user)
        return committed

    def can_stay_online(
        self,
        user_id: int,
        instance: int | str,
        *,
        counters: Mapping[int | str, int] | None = None,
    ) -> PeriodicQuotaDecision:
        now = self.clock()
        user = self._load_user(user_id)
        counters = counters or {
            active: self.traffic_counters(user_id, active)
            for state in user.quotas.values()
            if state.kind is PeriodicQuotaKind.TRAFFIC
            for active in state.starts
        }
        exhausted: list[str] = []
        remaining: list[float] = []
        resets: list[float] = []
        changed = False
        for key, state in user.quotas.items():
            if state.refresh_reset_if_due(now, counters=counters):
                changed = True
            snapshot = state.snapshot(now, counters)
            if snapshot.quota_finished:
                exhausted.append(key)
            else:
                active_count = len(state.starts)
                remaining.append(state.remaining_time(
                    now, active_count, counters=counters,
                    normal_user=self.is_normal_user(user_id),
                ))
            if state.next_reset is not None:
                resets.append(state.next_reset)
        if changed:
            self._persist(user_id, user)
        if exhausted:
            for key in exhausted:
                self.request_termination(user_id, key)
        return PeriodicQuotaDecision(
            allowed=not exhausted,
            exhausted_keys=tuple(exhausted),
            remaining_seconds=min(remaining) if remaining else None,
            next_reset=min(resets) if resets else None,
        )
