from datetime import time

from atd_radius.domain.billing_rules import ALL, VoipChargeRule
from atd_radius.infrastructure.voip_charge_rules import PostgresVoipChargeRuleRepository


class Result:
    def __init__(self, rows=()):
        self.rows = rows

    def fetchall(self):
        return self.rows


class Conn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM voip_charge_rules" in sql:
            if "WHERE charge_rule_id" in sql:
                return Result([(17, 8, time(8, 0), time(20, 0), 120, 5, 33)])
            return Result([(17, 8, time(8, 0), time(20, 0), 120, 5, 33)])
        if "FROM charge_rule_day_of_weeks" in sql:
            return Result([(0,), (2,), (4,)])
        if "FROM charge_rule_ports" in sql:
            return Result([("ppp0",), (ALL,)])
        raise AssertionError(sql)


def test_voip_charge_rule_maps_native_inherited_fields_and_child_tables():
    conn = Conn()
    rule = PostgresVoipChargeRuleRepository(conn).get(17)

    assert rule is not None
    assert rule.rule_id == 17
    assert rule.charge_id == 8
    assert rule.tariff_id == 33
    assert rule.time_limit == 120
    assert rule.start_second == 8 * 3600
    assert rule.end_second == 20 * 3600
    assert rule.days == frozenset({0, 2, 4})
    assert rule.ports == frozenset({"ppp0", ALL})
    assert rule.applies_to(__import__("datetime").datetime(2026, 10, 12, 10), 5, "ppp0")
    assert "FROM voip_charge_rules" in conn.calls[0][0]


def test_voip_rule_list_filters_by_native_charge_id():
    conn = Conn()
    rules = PostgresVoipChargeRuleRepository(conn).list(8)
    assert len(rules) == 1
    assert conn.calls[0][1] == (8,)
    assert "WHERE charge_id = %s" in conn.calls[0][0]


def test_voip_charge_rule_rejects_missing_native_identity():
    import pytest
    from atd_radius.domain.billing import BillingError

    with pytest.raises(BillingError):
        VoipChargeRule(
            rule_id=1,
            days=frozenset({0}),
            start_second=0,
            end_second=3600,
            charge_id=0,
            tariff_id=3,
        )
