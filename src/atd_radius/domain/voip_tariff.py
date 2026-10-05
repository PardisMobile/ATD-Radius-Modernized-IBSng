"""A1.24 VoIP tariff and prefix charging semantics."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING


@dataclass(frozen=True, slots=True)
class VoipPrefix:
    prefix_id: int
    code: str
    name: str
    cpm: Decimal
    free_seconds: int
    min_duration: int
    round_to: int
    min_chargeable_duration: int

    def __post_init__(self):
        if not self.code:
            raise ValueError("prefix code is required")
        if min(self.free_seconds, self.min_duration, self.round_to, self.min_chargeable_duration) < 0:
            raise ValueError("duration values cannot be negative")
        if self.cpm < 0:
            raise ValueError("cpm cannot be negative")


@dataclass(frozen=True, slots=True)
class VoipTariff:
    tariff_id: int
    name: str
    comment: str
    prefixes: tuple[VoipPrefix, ...]

    def find_prefix(self, called_number: str) -> VoipPrefix | None:
        matches = [p for p in self.prefixes if called_number.startswith(p.code)]
        return max(matches, key=lambda p: len(p.code), default=None)


def chargeable_duration(duration: int, prefix: VoipPrefix) -> int:
    if duration <= 0 or duration < prefix.min_duration:
        return 0
    result = max(duration - prefix.free_seconds, 0)
    if result and prefix.min_chargeable_duration and result < prefix.min_chargeable_duration:
        result = prefix.min_chargeable_duration
    if result and prefix.round_to:
        result = ((result + prefix.round_to - 1) // prefix.round_to) * prefix.round_to
    return result


def calculate_voip_charge(duration: int, prefix: VoipPrefix) -> Decimal:
    seconds = chargeable_duration(duration, prefix)
    return prefix.cpm * Decimal(seconds) / Decimal(60)
