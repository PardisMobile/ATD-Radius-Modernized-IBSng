from decimal import Decimal

import pytest

from atd_radius.domain.charge_usage import calculate_internet_instance_usage
from atd_radius.domain.billing_rules import InternetChargeRule


def rule(cpm="60", cpk="0.5"):
    return InternetChargeRule(
        rule_id=1,
        days=frozenset({0}),
        start_second=0,
        end_second=86399,
        cpm=Decimal(cpm),
        cpk=Decimal(cpk),
    )


def test_internet_charge_matches_a124_time_and_transfer_formula():
    assert calculate_internet_instance_usage(
        rule(), elapsed_seconds=120, input_octets=1024, output_octets=2048
    ) == Decimal("121")


def test_internet_charge_rejects_negative_usage():
    with pytest.raises(ValueError):
        calculate_internet_instance_usage(
            rule(), elapsed_seconds=-1, input_octets=0, output_octets=0
        )
