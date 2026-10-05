"""Accounting primitives for IBSng-compatible usage tracking."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class AccountingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    username: str
    session_id: str
    started_at: datetime
    ended_at: datetime | None = None
    input_octets: int = 0
    output_octets: int = 0

    @property
    def total_octets(self) -> int:
        if self.input_octets < 0 or self.output_octets < 0:
            raise AccountingError("octet counters cannot be negative")
        return self.input_octets + self.output_octets

    @property
    def duration_seconds(self) -> int:
        end = self.ended_at or datetime.now(timezone.utc)
        start = self.started_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        seconds = int((end - start).total_seconds())
        if seconds < 0:
            raise AccountingError("accounting end cannot precede start")
        return seconds


@dataclass(frozen=True, slots=True)
class AccountingPolicy:
    save_bw_usage: bool = False


def should_record_usage(policy: AccountingPolicy) -> bool:
    return policy.save_bw_usage


def usage_delta(previous: UsageSnapshot | None, current: UsageSnapshot) -> tuple[int, int]:
    """Return input/output delta, tolerating NAS counter resets."""
    if previous is None or previous.session_id != current.session_id:
        return current.input_octets, current.output_octets
    input_delta = current.input_octets - previous.input_octets
    output_delta = current.output_octets - previous.output_octets
    return max(input_delta, 0), max(output_delta, 0)
