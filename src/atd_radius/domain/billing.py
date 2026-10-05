"""Billing primitives for IBSng-compatible charge selection and usage pricing."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class BillingError(ValueError):
    pass


class ChargeKind(StrEnum):
    FLAT = "flat"
    TIME = "time"
    TRAFFIC = "traffic"
    SERVICE = "service"


@dataclass(frozen=True, slots=True)
class Charge:
    name: str
    kind: ChargeKind
    unit_price: Decimal
    currency: str = "IRR"
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.unit_price < 0:
            raise BillingError("unit price cannot be negative")
        if not self.currency:
            raise BillingError("currency is required")


@dataclass(frozen=True, slots=True)
class BillingUsage:
    seconds: int = 0
    octets: int = 0


def money(value: Decimal | str | int | float) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise BillingError("invalid monetary value") from exc


def calculate_charge(charge: Charge, usage: BillingUsage) -> Decimal:
    if not charge.enabled:
        return Decimal("0")
    if usage.seconds < 0 or usage.octets < 0:
        raise BillingError("usage counters cannot be negative")
    if charge.kind in (ChargeKind.FLAT, ChargeKind.SERVICE):
        units = Decimal("1")
    elif charge.kind is ChargeKind.TIME:
        units = Decimal(usage.seconds)
    else:
        units = Decimal(usage.octets)
    return charge.unit_price * units


def select_charge(normal: Charge | None, voip: Charge | None, is_voip: bool) -> Charge | None:
    selected = voip if is_voip else normal
    if selected is not None and not selected.enabled:
        return None
    return selected
