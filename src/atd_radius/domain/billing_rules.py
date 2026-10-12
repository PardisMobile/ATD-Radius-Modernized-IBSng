"""IBSng A1.24-compatible charge-rule selection and pricing primitives."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Mapping

from .billing import BillingError, BillingUsage


ALL = "_ALL_"


@dataclass(frozen=True, slots=True)
class ChargeRule:
    rule_id: int
    days: frozenset[int]
    start_second: int
    end_second: int
    ras_id: int | None = None
    ports: frozenset[str | None] = frozenset()

    def __post_init__(self) -> None:
        if not self.days:
            raise BillingError("charge rule must contain at least one day")
        if not all(0 <= day <= 6 for day in self.days):
            raise BillingError("invalid day of week")
        if not 0 <= self.start_second <= 86399 or not 0 <= self.end_second <= 86399:
            raise BillingError("invalid rule time")
        if self.end_second <= self.start_second:
            raise BillingError("charge rules cannot cross midnight")

    @property
    def priority(self) -> int:
        # A1.24: RAS-specific = +2, port-specific = +1.
        return (2 if self.ras_id is not None else 0) + (1 if ALL not in self.ports else 0)

    def applies_to(self, when: datetime, ras_id: int | None, port: str | None) -> bool:
        if when.weekday() not in self.days:
            return False
        second = when.hour * 3600 + when.minute * 60 + when.second
        if not (self.start_second <= second < self.end_second):
            return False
        if self.ras_id is not None and self.ras_id != ras_id:
            return False
        # A1.24 ChargeRule.anytimeAppliable requires either an exact port
        # membership or the explicit _ALL_ marker. An empty port set is not
        # a wildcard and therefore does not apply to any port.
        if port not in self.ports and ALL not in self.ports:
            return False
        return True


@dataclass(frozen=True, slots=True)
class InternetChargeRule(ChargeRule):
    cpm: Decimal = Decimal("0")
    cpk: Decimal = Decimal("0")
    assumed_kps: int = 0
    bandwidth_limit_kbytes: int = -1

    def __post_init__(self) -> None:
        ChargeRule.__post_init__(self)
        if self.cpm < 0 or self.cpk < 0:
            raise BillingError("charge rates cannot be negative")

    def calculate(self, usage: BillingUsage) -> Decimal:
        if usage.seconds < 0 or usage.octets < 0:
            raise BillingError("usage counters cannot be negative")
        return (self.cpm * Decimal(usage.seconds) / Decimal(60)) + (
            self.cpk * Decimal(usage.octets) / Decimal(1024)
        )


def select_effective_rule(
    rules: Iterable[ChargeRule],
    when: datetime,
    ras_id: int | None,
    port: str | None,
) -> ChargeRule:
    candidates = [rule for rule in rules if rule.applies_to(when, ras_id, port)]
    if not candidates:
        raise BillingError("no applicable charge rule")
    # A1.24 replaces the selected rule only when priority is strictly greater;
    # equal-priority rules therefore retain loader/input order.
    selected = candidates[0]
    for rule in candidates[1:]:
        if rule.priority > selected.priority:
            selected = rule
    return selected

@dataclass(frozen=True, slots=True)
class VoipChargeRule(ChargeRule):
    """A1.24 voip_charge_rules row mapped over the shared charge_rules fields."""

    charge_id: int = 0
    tariff_id: int = 0
    time_limit: int | None = None

    def __post_init__(self) -> None:
        ChargeRule.__post_init__(self)
        if self.charge_id <= 0 or self.tariff_id <= 0:
            raise BillingError("VoIP charge and tariff IDs must be positive")
        if self.time_limit is not None and self.time_limit < 0:
            raise BillingError("time limit cannot be negative")


def select_effective_voip_rule(
    rules: Iterable[VoipChargeRule],
    when: datetime,
    ras_id: int | None,
    port: str | None,
    called_number: str,
    tariffs: Mapping[int, object],
) -> VoipChargeRule:
    """Select an A1.24 VoIP rule, including called-number prefix applicability.

    A1.24 VoipChargeRule.anytimeAppliable rejects a rule when a non-empty
    called number has no prefix in that rule's tariff. An empty called number
    is treated as not acquired yet and does not block rule applicability.
    """
    candidates: list[VoipChargeRule] = []
    for rule in rules:
        if not rule.applies_to(when, ras_id, port):
            continue
        if called_number:
            tariff = tariffs.get(rule.tariff_id)
            if tariff is None:
                raise BillingError(f"VoIP tariff {rule.tariff_id} is missing")
            if tariff.find_prefix(called_number) is None:
                continue
        candidates.append(rule)
    if not candidates:
        raise BillingError("no applicable VoIP charge rule")
    selected = candidates[0]
    for rule in candidates[1:]:
        if rule.priority > selected.priority:
            selected = rule
    return selected
