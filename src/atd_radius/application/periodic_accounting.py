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
        assumed_kps: Callable[[int, int | str], float | None] | None = None,
        request_termination: Callable[[int, str], None] | None = None,
        is_normal_user: Callable[[int], bool] | None = None,
    ) -> None:
        self.attributes = attributes
        self.clock = clock
        self.traffic_counters = traffic_counters or (lambda user_id, instance: 0)
        self.assumed_kps = assumed_kps or (lambda user_id, instance: None)
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

    def reload_user(self, user_id: int) -> _UserState:
        """Apply source-shaped _reload semantics without losing live baselines."""
        attrs = self.attributes.load(user_id)
        current = self._users.get(user_id)
        if current is None:
            return self._load_user(user_id)
        now = self.clock()
        next_quotas: dict[str, PeriodicAccountingState] = {}
        configuration_changed = False
        for key, period, kind in self.DEFINITIONS:
            value = attrs.get(key)
            limit_raw = attrs.get(f"{key}_limit")
            if value in (None, "") or limit_raw in (None, ""):
                continue
            try:
                limit = int(limit_raw)
                usage = int(self._number(attrs, f"{key}_usage"))
                reset_raw = attrs.get(f"{key}_reset")
                reset = float(reset_raw) if reset_raw not in (None, "") else None
                config = PeriodicQuotaConfig(
                    key=key, period=period, kind=kind, value=str(value),
                    limit=limit, next_reset=reset, accumulated_usage=usage,
                )
            except (ValueError, TypeError, OverflowError):
                continue
            old = current.quotas.get(key)
            if old is None:
                next_quotas[key] = PeriodicAccountingState(config)
                continue
            changed_value = old.config.value != config.value
            configuration_changed = configuration_changed or changed_value
            old.config = config
            if changed_value:
                old.initial_usage = 0
                old.committed_usage = 0
                old.next_reset = None
                old.pending_reset_persist = True
                normal_user = self.is_normal_user(user_id)
                counters = {
                    instance: (
                        self.traffic_counters(user_id, instance)
                        if kind is not PeriodicQuotaKind.TRAFFIC or normal_user else 0
                    )
                    for instance in old.starts
                }
                old.refresh_reset_if_due(now, counters=counters)
            else:
                # A1.24 reloads the stored accumulated usage when the period
                # value is unchanged but retains current per-instance starts.
                old.initial_usage = 0
                old.committed_usage = usage
                if old.next_reset is None and reset is not None:
                    old.next_reset = reset
            next_quotas[key] = old
        current.quotas = next_quotas
        if configuration_changed:
            self._persist(user_id, current)
        return current

    @staticmethod
    def _baseline_attribute(key: str) -> str:
        return f"__periodic_start_{key}"

    def session_baseline_attributes(self, user_id: int, instance: int | str) -> Mapping[str, str]:
        """Serialize per-session quota baselines into the durable live-session snapshot."""
        user = self._load_user(user_id)
        values: dict[str, str] = {}
        for key, state in user.quotas.items():
            if instance not in state.starts:
                continue
            baseline = state.starts[instance]
            values[self._baseline_attribute(key)] = "none" if baseline is None else str(baseline)
            values[f"__periodic_value_{key}"] = state.config.value
        return values

    def restore_instance(
        self,
        user_id: int,
        instance: int | str,
        attributes: Mapping[str, str],
        *,
        fallback_started_at: float | None = None,
    ) -> None:
        """Restore active-session baselines after a process restart.

        Older snapshots without quota markers are backfilled from their durable
        RADIUS start timestamp; traffic counters begin at zero in that fallback.
        """
        user = self.reload_user(user_id)
        for key, state in user.quotas.items():
            marker = self._baseline_attribute(key)
            stored_value = attributes.get(f"__periodic_value_{key}")
            if marker in attributes and stored_value not in (None, state.config.value):
                # A1.24 _reload resets active starts when the period value changes.
                state.starts[instance] = (
                    self.clock()
                    if state.kind is PeriodicQuotaKind.TIME
                    else self.traffic_counters(user_id, instance)
                )
            elif marker in attributes:
                raw = str(attributes[marker])
                if raw == "none":
                    state.starts[instance] = None
                else:
                    try:
                        state.starts[instance] = (
                            float(raw)
                            if state.kind is PeriodicQuotaKind.TIME
                            else (
                                int(float(raw)) if self.is_normal_user(user_id) else 0
                            )
                        )
                    except (TypeError, ValueError, OverflowError):
                        raise ValueError(f"invalid persisted periodic baseline for {key}")
            elif fallback_started_at is not None and instance not in state.starts:
                state.starts[instance] = (
                    fallback_started_at
                    if state.kind is PeriodicQuotaKind.TIME else 0
                )

    def can_login(self, user_id: int) -> PeriodicQuotaDecision:
        """Pre-admission check matching A1.24's login-time quota rejection."""
        now = self.clock()
        user = self.reload_user(user_id)
        normal_user = self.is_normal_user(user_id)
        counters = {
            instance: (
                self.traffic_counters(user_id, instance) if normal_user else 0
            )
            for state in user.quotas.values()
            if state.kind is PeriodicQuotaKind.TRAFFIC
            for instance in state.starts
        }
        exhausted: list[str] = []
        changed = False
        for key, state in user.quotas.items():
            if state.refresh_reset_if_due(now, counters=counters):
                changed = True
            if state.kind is PeriodicQuotaKind.TRAFFIC and not normal_user:
                continue
            if state.snapshot(now, counters).quota_finished:
                exhausted.append(key)
        if changed:
            self._persist(user_id, user)
        return PeriodicQuotaDecision(not exhausted, tuple(exhausted))

    def has_quotas(self, user_id: int) -> bool:
        """Return whether the effective user configuration enables any quota."""
        return bool(self._load_user(user_id).quotas)

    def _persist(self, user_id: int, user: _UserState) -> None:
        values: dict[str, str] = {}
        for key, state in user.quotas.items():
            values[f"{key}_usage"] = str(state.committed_usage + state.initial_usage)
            values[f"{key}_reset"] = str(state.next_reset or 0)
        if values:
            self.attributes.save(user_id, values)
            for state in user.quotas.values():
                if state.next_reset is not None and state.next_reset > 0:
                    state.pending_reset_persist = False

    def login(
        self, user_id: int, instance: int | str, *, start_accounting: bool = False
    ) -> PeriodicQuotaDecision:
        now = self.clock()
        user = self.reload_user(user_id)
        normal_user = self.is_normal_user(user_id)
        exhausted: list[str] = []
        counters = {
            active_instance: (
                self.traffic_counters(user_id, active_instance) if normal_user else 0
            )
            for state in user.quotas.values()
            if state.kind is PeriodicQuotaKind.TRAFFIC
            for active_instance in state.starts
        }
        counters[instance] = self.traffic_counters(user_id, instance) if normal_user else 0
        for key, state in user.quotas.items():
            traffic = (
                counters[instance]
                if state.kind is PeriodicQuotaKind.TRAFFIC and normal_user else 0
            )
            finished = state.login(
                instance, now, traffic, counters, start_accounting=start_accounting
            )
            if finished and not (
                state.kind is PeriodicQuotaKind.TRAFFIC and not normal_user
            ):
                exhausted.append(key)
        self._persist(user_id, user)
        return PeriodicQuotaDecision(not exhausted, tuple(exhausted))

    def update(self, user_id: int, instance: int | str, *, start_accounting: bool = False) -> PeriodicQuotaDecision:
        now = self.clock()
        user = self.reload_user(user_id)
        normal_user = self.is_normal_user(user_id)
        counters = {
            active_instance: (
                self.traffic_counters(user_id, active_instance) if normal_user else 0
            )
            for state in user.quotas.values()
            if state.kind is PeriodicQuotaKind.TRAFFIC
            for active_instance in state.starts
        }
        if start_accounting:
            for state in user.quotas.values():
                state.update_baseline(
                    instance, now,
                    counters.get(instance, 0)
                    if state.kind is PeriodicQuotaKind.TRAFFIC and normal_user else 0,
                )
        self._persist(user_id, user)
        return self.can_stay_online(user_id, instance, counters=counters)

    def logout(self, user_id: int, instance: int | str) -> Mapping[str, int | float]:
        now = self.clock()
        user = self.reload_user(user_id)
        normal_user = self.is_normal_user(user_id)
        committed: dict[str, int | float] = {}
        for key, state in user.quotas.items():
            traffic = (
                self.traffic_counters(user_id, instance)
                if state.kind is PeriodicQuotaKind.TRAFFIC and normal_user else 0
            )
            if state.kind is PeriodicQuotaKind.TRAFFIC and not normal_user and instance in state.starts:
                state.starts[instance] = 0 if state.starts[instance] is not None else None
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
        user = self.reload_user(user_id)
        normal_user = self.is_normal_user(user_id)
        counters = counters or {
            active: (self.traffic_counters(user_id, active) if normal_user else 0)
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
            if snapshot.quota_finished and not (
                state.kind is PeriodicQuotaKind.TRAFFIC and not normal_user
            ):
                exhausted.append(key)
            else:
                active_count = len(state.starts)
                speeds = {
                    active: speed
                    for active in state.starts
                    if (speed := self.assumed_kps(user_id, active)) is not None and speed > 0
                }
                remaining.append(state.remaining_time(
                    now, active_count, counters=counters, assumed_kps=speeds,
                    normal_user=normal_user,
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
