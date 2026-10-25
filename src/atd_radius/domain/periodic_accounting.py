"""A1.24 periodic-accounting quota calculations.

This module captures the legacy plugin's arithmetic and per-instance baselines.
Persistence, Gregorian/Jalali month-boundary helpers, and runtime hook wiring
are deliberately injected/handled by the application layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import inf
from typing import Callable, Mapping


class PeriodicQuotaKind(StrEnum):
    TIME = "time"
    TRAFFIC = "traffic"


@dataclass(frozen=True, slots=True)
class PeriodicQuotaConfig:
    key: str
    period: str
    kind: PeriodicQuotaKind
    value: str
    limit: int
    next_reset: float | None = None
    accumulated_usage: int = 0

    def __post_init__(self) -> None:
        if self.period not in {"daily", "monthly"}:
            raise ValueError("period must be daily or monthly")
        if self.limit < 0 or self.accumulated_usage < 0:
            raise ValueError("quota limit and accumulated usage must be non-negative")
        if self.period == "daily":
            try:
                interval = int(self.value)
            except (TypeError, ValueError) as exc:
                raise ValueError("daily period value must be a positive integer") from exc
            if interval <= 0:
                raise ValueError("daily period value must be a positive integer")
        elif self.value not in {"gregorian", "jalali"}:
            raise ValueError("monthly period value must be 'gregorian' or 'jalali'")


@dataclass(frozen=True, slots=True)
class PeriodicQuotaSnapshot:
    usage: int
    remaining: int
    quota_finished: bool
    next_reset: float
    reset_required: bool = False


@dataclass(slots=True)
class PeriodicAccountingState:
    """In-memory lifecycle state matching BasePeriodicAccounting's accounting.

    Each session/instance owns a baseline. Time quotas use epoch seconds;
    traffic quotas use total input+output octets. A completed instance is
    committed into accumulated usage exactly once by removing its baseline.
    """
    config: PeriodicQuotaConfig
    initial_usage: int = 0
    committed_usage: int = 0
    next_reset: float | None = None
    starts: dict[int, float | int] = field(default_factory=dict)
    pending_reset_persist: bool = False

    def __post_init__(self) -> None:
        if self.initial_usage < 0 or self.committed_usage < 0:
            raise ValueError("usage values must be non-negative")
        self.next_reset = self.config.next_reset if self.next_reset is None else self.next_reset
        if self.next_reset is None:
            self.pending_reset_persist = True

    @property
    def kind(self) -> PeriodicQuotaKind:
        return self.config.kind

    def current_usage(self, now: float, counters: Mapping[int, int] | None = None) -> int:
        total = self.initial_usage + self.committed_usage
        counters = counters or {}
        for instance, start in self.starts.items():
            if self.kind is PeriodicQuotaKind.TIME:
                total += max(0, int(now - float(start)))
            else:
                total += max(0, int(counters.get(instance, 0)) - int(start))
        return total

    def snapshot(
        self, now: float, counters: Mapping[int, int] | None = None
    ) -> PeriodicQuotaSnapshot:
        usage = self.current_usage(now, counters)
        remaining = max(0, self.config.limit - usage)
        reset = float(self.next_reset or 0)
        return PeriodicQuotaSnapshot(
            usage=usage,
            remaining=remaining,
            quota_finished=usage >= self.config.limit,
            next_reset=reset,
            reset_required=self.pending_reset_persist,
        )

    def login(self, instance: int, now: float, traffic_octets: int = 0) -> bool:
        """Register a new instance baseline; return whether quota is exhausted.

        A1.24 captures the start baseline before checking the quota on login.
        """
        if instance < 1 or traffic_octets < 0:
            raise ValueError("instance must be positive and traffic must be non-negative")
        self.starts[instance] = now if self.kind is PeriodicQuotaKind.TIME else traffic_octets
        return self.current_usage(now, {instance: traffic_octets}) >= self.config.limit

    def update_baseline(self, instance: int, now: float, traffic_octets: int = 0) -> None:
        if instance < 1 or traffic_octets < 0:
            raise ValueError("instance must be positive and traffic must be non-negative")
        if instance in self.starts:
            self.starts[instance] = now if self.kind is PeriodicQuotaKind.TIME else traffic_octets

    def logout(self, instance: int, now: float, traffic_octets: int = 0) -> int:
        """Commit usage for one instance and remove its active baseline."""
        start = self.starts.pop(instance, None)
        if start is None:
            return 0
        if self.kind is PeriodicQuotaKind.TIME:
            used = max(0, int(now - float(start)))
        else:
            used = max(0, int(traffic_octets) - int(start))
        self.committed_usage += used
        return used

    def reset(self, next_reset: float) -> None:
        if next_reset <= 0:
            raise ValueError("next reset must be a positive epoch timestamp")
        self.initial_usage = 0
        self.committed_usage = 0
        self.starts.clear()
        self.next_reset = float(next_reset)
        self.pending_reset_persist = True

    def refresh_reset_if_due(
        self,
        now: float,
        next_month_reset: Callable[[str], float] | None = None,
    ) -> bool:
        """Reset usage when due; return True when a reset was performed.

        Daily intervals preserve A1.24's anchored schedule: extend the stored
        reset epoch by N days until it is no longer in the past. Monthly
        boundaries are delegated to the source-compatible Gregorian/Jalali
        calendar helpers; no approximate month length is used here.
        """
        if self.next_reset is None:
            if self.config.period == "daily":
                base = now - (now % 86400)
                interval = int(self.config.value) * 86400
                next_reset = base + interval
                while next_reset < now:
                    next_reset += interval
            else:
                if next_month_reset is None:
                    raise ValueError("monthly reset requires source-compatible calendar helper")
                next_reset = next_month_reset(self.config.value)
            self.reset(next_reset)
            return True
        if self.next_reset > now:
            return False
        if self.config.period == "daily":
            interval = int(self.config.value) * 86400
            next_reset = self.next_reset
            while next_reset <= now:
                next_reset += interval
        else:
            if next_month_reset is None:
                raise ValueError("monthly reset requires source-compatible calendar helper")
            next_reset = next_month_reset(self.config.value)
        self.reset(next_reset)
        return True

    def remaining_time(
        self,
        now: float,
        instances: int,
        counters: Mapping[int, int] | None = None,
        assumed_kps: Mapping[int, float] | None = None,
        normal_user: bool = True,
    ) -> float:
        """A1.24's estimated time until quota exhaustion across active instances."""
        if instances <= 0:
            return inf
        remaining = self.config.limit - self.current_usage(now, counters)
        if remaining <= 0:
            return 0.0
        share = remaining / instances
        if self.kind is PeriodicQuotaKind.TIME:
            return share
        if not normal_user:
            return inf
        speeds = assumed_kps or {}
        result = 0.0
        for instance in range(1, instances + 1):
            speed = speeds.get(instance)
            if speed is not None and speed > 0:
                result += share / (speed * 1024.0)
        return result
