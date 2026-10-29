"""A1.24 periodic-accounting quota calculations.

This module captures the legacy plugin's arithmetic and per-instance baselines.
Persistence and runtime hook wiring are deliberately handled by the application
layer; Gregorian/Jalali month-boundary math is ported from the canonical source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import time
from enum import StrEnum
from math import inf
from typing import Callable, Mapping


_GREGORIAN_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_JALALI_MONTH_DAYS = (31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29)


def _gregorian_to_jalali(year: int, month: int, day: int) -> tuple[int, int, int]:
    """Integer-division port of IBSng A1.24 core/lib/jalali.py."""
    gy, gm, gd = year - 1600, month - 1, day - 1
    gday = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for index in range(gm):
        gday += _GREGORIAN_MONTH_DAYS[index]
    if gm > 1 and (gy % 4 == 0 and gy % 100 != 0 or gy % 400 == 0):
        gday += 1
    gday += gd
    jday = gday - 79
    jnp = jday // 12053
    jday %= 12053
    jy = 979 + 33 * jnp + 4 * (jday // 1461)
    jday %= 1461
    if jday >= 366:
        jy += (jday - 1) // 365
        jday = (jday - 1) % 365
    index = 0
    for index in range(11):
        if jday < _JALALI_MONTH_DAYS[index]:
            index -= 1
            break
        jday -= _JALALI_MONTH_DAYS[index]
    return jy, index + 2, jday + 1


def _jalali_to_gregorian(year: int, month: int, day: int) -> tuple[int, int, int]:
    """Integer-division port of IBSng A1.24 core/lib/jalali.py."""
    jy, jm, jd = year - 979, month - 1, day - 1
    jday = 365 * jy + (jy // 33) * 8 + ((jy % 33 + 3) // 4)
    for index in range(jm):
        jday += _JALALI_MONTH_DAYS[index]
    jday += jd
    gday = jday + 79
    gy = 1600 + 400 * (gday // 146097)
    gday %= 146097
    leap = 1
    if gday >= 36525:
        gday -= 1
        gy += 100 * (gday // 36524)
        gday %= 36524
        if gday >= 365:
            gday += 1
        else:
            leap = 0
    gy += 4 * (gday // 1461)
    gday %= 1461
    if gday >= 366:
        leap = 0
        gday -= 1
        gy += gday // 365
        gday %= 365
    month_index = 0
    while gday >= _GREGORIAN_MONTH_DAYS[month_index] + (1 if month_index == 1 and leap else 0):
        gday -= _GREGORIAN_MONTH_DAYS[month_index] + (1 if month_index == 1 and leap else 0)
        month_index += 1
    return gy, month_index + 1, gday + 1


def a124_next_month_reset(calendar: str, now: float | None = None) -> float:
    """Exact local-midnight month boundary used by A1.24 time_lib.py."""
    if calendar not in {"gregorian", "jalali"}:
        raise ValueError("calendar must be 'gregorian' or 'jalali'")
    local = time.localtime(time.time() if now is None else now)
    year, month, day = local[:3]
    if calendar == "gregorian":
        return time.mktime((year, month + 1, 1, 0, 0, 0, 0, 0, -1))
    jyear, jmonth, _ = _gregorian_to_jalali(year, month, day)
    jmonth += 1
    if jmonth > 12:
        jyear += 1
        jmonth = 1
    gyear, gmonth, gday = _jalali_to_gregorian(jyear, jmonth, 1)
    return time.mktime((gyear, gmonth, gday, 0, 0, 0, 0, 0, -1))


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
    accumulated_usage: int | float = 0

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
    usage: int | float
    remaining: int | float
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
    initial_usage: int | float = 0
    committed_usage: int | float | None = None
    next_reset: float | None = None
    starts: dict[int | str, float | int | None] = field(default_factory=dict)
    pending_reset_persist: bool = False

    def __post_init__(self) -> None:
        if self.committed_usage is None:
            self.committed_usage = self.config.accumulated_usage
        if self.initial_usage < 0 or self.committed_usage < 0:
            raise ValueError("usage values must be non-negative")
        self.next_reset = self.config.next_reset if self.next_reset is None else self.next_reset
        if self.next_reset is None:
            self.pending_reset_persist = True

    @property
    def kind(self) -> PeriodicQuotaKind:
        return self.config.kind

    def current_usage(self, now: float, counters: Mapping[int | str, int] | None = None) -> int | float:
        total = self.initial_usage + self.committed_usage
        counters = counters or {}
        for instance, start in self.starts.items():
            if start is None:
                continue
            if self.kind is PeriodicQuotaKind.TIME:
                total += now - float(start)
            else:
                total += int(counters.get(instance, int(start))) - int(start)
        return total

    def snapshot(
        self, now: float, counters: Mapping[int | str, int] | None = None
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

    @staticmethod
    def _valid_instance(instance: int | str) -> bool:
        return (isinstance(instance, int) and not isinstance(instance, bool) and instance > 0) or (isinstance(instance, str) and bool(instance.strip()))

    def login(
        self, instance: int | str, now: float, traffic_octets: int = 0,
        counters: Mapping[int | str, int] | None = None,
        start_accounting: bool = True,
    ) -> bool:
        """Register a new instance baseline; return whether quota is exhausted.

        A1.24 captures the start baseline before checking the quota on login.
        """
        if not self._valid_instance(instance) or traffic_octets < 0:
            raise ValueError("instance must be a positive integer or non-empty string; traffic must be non-negative")
        self.starts[instance] = (
            (now if self.kind is PeriodicQuotaKind.TIME else traffic_octets)
            if start_accounting else None
        )
        current_counters = dict(counters or {})
        current_counters[instance] = traffic_octets
        return self.current_usage(now, current_counters) >= self.config.limit

    def update_baseline(self, instance: int | str, now: float, traffic_octets: int = 0) -> None:
        if not self._valid_instance(instance) or traffic_octets < 0:
            raise ValueError("instance must be a positive integer or non-empty string; traffic must be non-negative")
        if instance in self.starts:
            self.starts[instance] = now if self.kind is PeriodicQuotaKind.TIME else traffic_octets

    def logout(self, instance: int | str, now: float, traffic_octets: int = 0) -> int | float:
        """Commit usage for one instance and remove its active baseline."""
        if instance not in self.starts:
            return 0
        start = self.starts.pop(instance)
        if start is None:
            return 0
        if self.kind is PeriodicQuotaKind.TIME:
            used = now - float(start)
        else:
            used = int(traffic_octets) - int(start)
        self.committed_usage += used
        return used

    def reset(
        self, next_reset: float, now: float, counters: Mapping[int, int] | None = None
    ) -> None:
        if next_reset <= 0:
            raise ValueError("next reset must be a positive epoch timestamp")
        counters = counters or {}
        # A1.24 resets accumulated usage but immediately rebases every active
        # instance, so its post-reset traffic/time is charged to the new period.
        self.starts = {
            instance: (now if self.kind is PeriodicQuotaKind.TIME else int(counters.get(instance, 0)))
            for instance in self.starts
        }
        self.initial_usage = 0
        self.committed_usage = 0
        self.next_reset = float(next_reset)
        self.pending_reset_persist = True

    def refresh_reset_if_due(
        self,
        now: float,
        next_month_reset: Callable[[str], float] | None = None,
        counters: Mapping[int, int] | None = None,
    ) -> bool:
        """Reset usage when due; return True when a reset was performed.

        Daily intervals preserve A1.24's anchored schedule: extend the stored
        reset epoch by N days until it is no longer in the past. Monthly
        boundaries are delegated to the source-compatible Gregorian/Jalali
        calendar helpers; no approximate month length is used here.
        """
        if self.next_reset is None:
            if self.config.period == "daily":
                base = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                interval = int(self.config.value) * 86400
                next_reset = base + interval
                while next_reset < now:
                    next_reset += interval
            else:
                next_reset = (
                    a124_next_month_reset(self.config.value, now)
                    if next_month_reset is None
                    else next_month_reset(self.config.value)
                )
            self.reset(next_reset, now, counters)
            return True
        # A1.24 considers the reset due at equality (next_reset <= now).
        # The reset calculation below then advances from the saved boundary
        # by one interval before catching up with its strict candidate < now loop.
        if self.next_reset > now:
            return False
        if self.config.period == "daily":
            interval = int(self.config.value) * 86400
            # A1.24 first advances from the saved boundary by one whole
            # interval, then catches up while the candidate is strictly
            # earlier than now. Equality is intentionally retained: a later
            # hook at that exact epoch will advance from it again.
            next_reset = self.next_reset + interval
            while next_reset < now:
                next_reset += interval
        else:
            next_reset = (
                a124_next_month_reset(self.config.value, now)
                if next_month_reset is None
                else next_month_reset(self.config.value)
            )
        self.reset(next_reset, now, counters)
        return True

    def remaining_time(
        self,
        now: float,
        instances: int,
        counters: Mapping[int, int] | None = None,
        assumed_kps: Mapping[int | str, float] | None = None,
        normal_user: bool = True,
    ) -> float:
        """A1.24's estimated time until quota exhaustion across active instances."""
        if instances <= 0:
            return inf
        remaining = self.config.limit - self.current_usage(now, counters)
        if remaining <= 0:
            return 0.0
        share = remaining / instances if self.kind is PeriodicQuotaKind.TIME else remaining // instances
        if self.kind is PeriodicQuotaKind.TIME:
            return share
        if not normal_user:
            return inf
        speeds = assumed_kps or {}
        result = 0.0
        # Runtime instances use durable composite RAS/session keys. Keep the
        # legacy 1-based fallback for domain callers that supply only a count.
        active_instances = tuple(self.starts) or tuple(range(1, instances + 1))
        for instance in active_instances:
            speed = speeds.get(instance)
            if speed is not None and speed > 0:
                result += share / (speed * 1024.0)
        return result
