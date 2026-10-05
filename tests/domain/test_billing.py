from decimal import Decimal

import pytest

from atd_radius.domain.billing import (
    BillingError,
    BillingUsage,
    Charge,
    ChargeKind,
    calculate_charge,
    select_charge,
)


def test_flat_and_service_charges_are_one_unit():
    assert calculate_charge(Charge("f", ChargeKind.FLAT, Decimal("100")), BillingUsage(seconds=90)) == Decimal("100")
    assert calculate_charge(Charge("s", ChargeKind.SERVICE, Decimal("250")), BillingUsage(octets=999)) == Decimal("250")


def test_time_and_traffic_charges_use_usage_units():
    assert calculate_charge(Charge("t", ChargeKind.TIME, Decimal("2")), BillingUsage(seconds=30)) == Decimal("60")
    assert calculate_charge(Charge("b", ChargeKind.TRAFFIC, Decimal("0.5")), BillingUsage(octets=100)) == Decimal("50.0")


def test_normal_and_voip_charge_selection():
    normal = Charge("normal", ChargeKind.FLAT, Decimal("10"))
    voip = Charge("voip", ChargeKind.FLAT, Decimal("20"))
    assert select_charge(normal, voip, False) == normal
    assert select_charge(normal, voip, True) == voip


def test_negative_usage_is_rejected():
    charge = Charge("t", ChargeKind.TIME, Decimal("1"))
    with pytest.raises(BillingError):
        calculate_charge(charge, BillingUsage(seconds=-1))
