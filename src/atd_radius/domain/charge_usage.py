"""Source-traced A1.24 charge usage primitives for accounting settlement."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .billing import BillingUsage
from .billing_rules import InternetChargeRule


class ChargeRuleSource(Protocol):
    def list(self, charge_id: int | None = None) -> list[InternetChargeRule]: ...


@dataclass(frozen=True, slots=True)
class ChargeUsageSnapshot:
    """Usage for one A1.24 user instance at logout."""
    elapsed_seconds: int
    octets: int

    def as_billing_usage(self) -> BillingUsage:
        return BillingUsage(seconds=self.elapsed_seconds, octets=self.octets)


def calculate_internet_instance_usage(
    rule: InternetChargeRule,
    *,
    elapsed_seconds: int,
    input_octets: int,
    output_octets: int,
) -> Decimal:
    """Match A1.24 InternetChargeRule.cpm/cpk calculation exactly."""
    return rule.calculate(
        BillingUsage(
            seconds=elapsed_seconds,
            octets=input_octets + output_octets,
        )
    )
