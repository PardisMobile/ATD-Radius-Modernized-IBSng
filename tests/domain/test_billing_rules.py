from datetime import datetime
from decimal import Decimal

import pytest

from atd_radius.domain.billing import BillingUsage, BillingError
from atd_radius.domain.billing_rules import (
    ALL,
    InternetChargeRule,
    VoipChargeRule,
    select_effective_rule,
    select_effective_voip_rule,
)
from atd_radius.domain.voip_tariff import VoipPrefix, VoipTariff


def rule(rule_id, *, ras_id=None, ports=frozenset({ALL})):
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


def test_rule_start_is_inclusive_like_a124_interval():
    when = datetime(2026, 10, 5, 0, 0, 0)
    selected = select_effective_rule([rule(8)], when, ras_id=None, port="ppp0")
    assert selected.rule_id == 8


def test_equal_priority_keeps_loader_order():
    when = datetime(2026, 10, 5, 12, 0, 0)
    selected = select_effective_rule(
        [rule(20, ras_id=10), rule(21, ras_id=10)],
        when,
        ras_id=10,
        port="ppp0",
    )
    assert selected.rule_id == 20


def test_empty_port_list_is_not_a_wildcard_in_a124():
    when = datetime(2026, 10, 5, 12, 0, 0)
    with pytest.raises(BillingError, match="no applicable"):
        select_effective_rule(
            [rule(30, ras_id=10, ports=frozenset())],
            when,
            ras_id=10,
            port="ppp0",
        )



def voip_rule(rule_id, tariff_id, *, ras_id=None, ports=frozenset({ALL})):
    return VoipChargeRule(
        rule_id=rule_id, days=frozenset({0}), start_second=0, end_second=86399,
        ras_id=ras_id, ports=ports, charge_id=4, tariff_id=tariff_id,
    )


def tariff(tariff_id, codes):
    return VoipTariff(
        tariff_id, f"tariff-{tariff_id}", "",
        tuple(
            VoipPrefix(i + 1, code, code, Decimal("1"), 0, 0, 0, 0)
            for i, code in enumerate(codes)
        ),
    )


def test_voip_rule_selection_requires_tariff_prefix_for_nonempty_called_number():
    when = datetime(2026, 10, 5, 12, 0, 0)
    rules = [voip_rule(1, 10, ras_id=10, ports=frozenset({"ppp0"})),
             voip_rule(2, 11, ras_id=10, ports=frozenset({"ppp0"}))]
    selected = select_effective_voip_rule(
        rules, when, 10, "ppp0", "9891212",
        {10: tariff(10, ["1", "44"]), 11: tariff(11, ["98", "989"])},
    )
    assert selected.rule_id == 2


def test_voip_rule_selection_rejects_when_no_tariff_matches_called_number():
    when = datetime(2026, 10, 5, 12, 0, 0)
    with pytest.raises(BillingError, match="no applicable VoIP"):
        select_effective_voip_rule(
            [voip_rule(1, 10)], when, 10, "ppp0", "9891212",
            {10: tariff(10, ["44", "1"])},
        )


def test_voip_rule_selection_allows_empty_called_number_before_ras_acquires_it():
    when = datetime(2026, 10, 5, 12, 0, 0)
    selected = select_effective_voip_rule(
        [voip_rule(1, 999)], when, 10, "ppp0", "", {},
    )
    assert selected.rule_id == 1
