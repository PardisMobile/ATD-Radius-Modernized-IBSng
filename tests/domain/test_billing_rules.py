from datetime import datetime
from decimal import Decimal

import pytest

from atd_radius.domain.billing import BillingUsage, BillingError
from atd_radius.domain.billing_rules import ALL, InternetChargeRule, select_effective_rule


def rule(rule_id, *, ras_id=None, ports=frozenset()):
    return InternetChargeRule(
        rule_id=rule_id,
        days=frozenset({0}),
        start_second=0,
        end_second=86399,
        ras_id=ras_id,
        ports=ports,
        cpm=Decimal("60"),
        cpk=Decimal("1"),
    )


def test_a124_rule_priority_prefers_ras_and_port_specific():
    when = datetime(2026, 10, 5, 12, 0, 0)
    selected = select_effective_rule(
        [
            rule(1, ras_id=None, ports=frozenset({ALL})),
            rule(2, ras_id=10, ports=frozenset({ALL})),
            rule(3, ras_id=10, ports=frozenset({"ppp0"})),
        ],
        when,
        ras_id=10,
        port="ppp0",
    )
    assert selected.rule_id == 3
    assert selected.priority == 3


def test_a124_wildcard_port_rule_applies_on_matching_ras():
    when = datetime(2026, 10, 5, 12, 0, 0)
    selected = select_effective_rule(
        [rule(7, ras_id=10, ports=frozenset({ALL}))],
        when,
        ras_id=10,
        port="ppp0",
    )
    assert selected.rule_id == 7


def test_internet_charge_matches_a124_cpm_and_cpk_units():
    r = rule(1)
    assert r.calculate(BillingUsage(seconds=60, octets=1024)) == Decimal("61")


def test_no_rule_is_an_error():
    when = datetime(2026, 10, 5, 12, 0, 0)
    with pytest.raises(BillingError, match="no applicable"):
        select_effective_rule([rule(1, ras_id=10)], when, ras_id=20, port="ppp0")
