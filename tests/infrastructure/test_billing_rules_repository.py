from datetime import time
from decimal import Decimal

from atd_radius.infrastructure.billing_rules import PostgresInternetChargeRuleRepository


class Result:
    def __init__(self, rows):
        self.rows = rows
    def fetchall(self):
        return self.rows


class Conn:
    def execute(self, sql, params=()):
        if "FROM internet_charge_rules" in sql:
            return Result([(7, time(0, 0), time(23, 59, 59), 10, Decimal("60"), Decimal("1"), 128, 4096)])
        if "FROM charge_rule_day_of_weeks" in sql:
            return Result([(0,), (1,)])
        if "FROM charge_rule_ports" in sql:
            return Result([("ppp0",)])
        raise AssertionError(sql)


def test_repository_maps_native_internet_charge_rule_tables():
    rule = PostgresInternetChargeRuleRepository(Conn()).get(7)
    assert rule is not None
    assert rule.rule_id == 7
    assert rule.ras_id == 10
    assert rule.days == frozenset({0, 1})
    assert rule.ports == frozenset({"ppp0"})
    assert rule.cpm == Decimal("60")
    assert rule.cpk == Decimal("1")
    assert rule.assumed_kps == 128
    assert rule.bandwidth_limit_kbytes == 4096
