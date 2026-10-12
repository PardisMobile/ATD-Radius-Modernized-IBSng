from datetime import time
from decimal import Decimal

from atd_radius.infrastructure.billing_rules import PostgresInternetChargeRuleRepository


class Result:
    def __init__(self, rows):
        self.rows = rows
    def fetchall(self):
        return self.rows
    def fetchone(self):
        return self.rows[0] if self.rows else None


class Conn:
    def execute(self, sql, params=()):
        if "FROM internet_charge_rules" in sql:
            return Result([(7, time(0, 0), time(23, 59, 59), 10, Decimal("60"), Decimal("1"), 128, 4096, None, None, 5)])
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
    assert rule.charge_id == 5
    assert rule.bw_transmit_leaf_id is None
    assert rule.bw_receive_leaf_id is None


from atd_radius.infrastructure.billing_rules import (
    InternetChargeRuleInput,
    InternetChargeNotFound,
    InternetChargeTypeError,
    InternetRuleConflictError,
    InternetRuleInputError,
)


class MutationConn:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if not self.responses:
            return Result([])
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def internet_payload(**changes):
    values = dict(
        start_time="08:00", end_time="18:00", days=("Monday", "Tuesday"),
        cpm=Decimal("2.50"), cpk=Decimal("0.25"), assumed_kps=128,
        bandwidth_limit_kbytes=4096, tx_leaf_name="", rx_leaf_name="",
        ras_id=None, ports=("_ALL_",),
    )
    values.update(changes)
    return InternetChargeRuleInput(**values)


def test_internet_rule_create_writes_native_columns_and_sequence():
    conn = MutationConn([
        Result([(5, "Internet")]), Result([]), Result([(31,)]),
        Result([]), Result([]), Result([]), Result([]),
    ])
    rule_id = PostgresInternetChargeRuleRepository(conn).create("Broadband", internet_payload())
    assert rule_id == 31
    insert = next((sql, params) for sql, params in conn.calls if "INSERT INTO internet_charge_rules" in sql)
    assert "bw_transmit_leaf_id" in insert[0]
    assert "bw_receive_leaf_id" in insert[0]
    assert insert[1] == (5, 31, "08:00:00", "18:00:00", Decimal("2.50"), Decimal("0.25"), 128, 4096, None, None, None)


def test_internet_rule_validation_requires_positive_assumed_kps_and_leaf_pair():
    repo = PostgresInternetChargeRuleRepository(MutationConn([]))
    with pytest.raises(InternetRuleInputError, match="assumed_kps"):
        repo._validate(internet_payload(assumed_kps=0))
    with pytest.raises(InternetRuleInputError, match="both be set"):
        repo._require_leaf_pair("tx", "")


def test_internet_rule_rejects_wrong_charge_type():
    repo = PostgresInternetChargeRuleRepository(MutationConn([Result([(5, "VoIP")])]))
    with pytest.raises(InternetChargeTypeError):
        repo.create("Calls", internet_payload())


def test_internet_rule_detects_native_overlap_for_same_ras_port_day_time():
    conn = MutationConn([
        Result([(5, "Internet")]),
        Result([(17, time(9), time(17), None)]),
        Result([("_ALL_",)]), Result([(0,)]),
    ])
    with pytest.raises(InternetRuleConflictError):
        PostgresInternetChargeRuleRepository(conn).create(
            "Broadband", internet_payload(start_time="10:00", end_time="12:00", days=("Monday",))
        )


def test_internet_rule_delete_removes_children_before_rule_row():
    conn = MutationConn([
        Result([(5, "Internet")]), Result([(31,)]),
        Result([]), Result([]), Result([]),
    ])
    PostgresInternetChargeRuleRepository(conn).delete("Broadband", 31)
    statements = [sql for sql, _ in conn.calls]
    rule_delete = next(i for i, sql in enumerate(statements) if "DELETE FROM internet_charge_rules" in sql)
    assert statements.index("DELETE FROM charge_rule_ports WHERE charge_rule_id=%s") < rule_delete
    assert statements.index("DELETE FROM charge_rule_day_of_weeks WHERE charge_rule_id=%s") < rule_delete
