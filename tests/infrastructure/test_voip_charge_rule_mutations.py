from datetime import time

import pytest

from atd_radius.domain.billing_rules import ALL
from atd_radius.infrastructure.voip_charge_rules import (
    ChargeNotFound,
    ChargeTypeError,
    PostgresVoipChargeRuleRepository,
    VoipChargeRuleInput,
    VoipRuleConflictError,
)


class Result:
    def __init__(self, rows=(), row=None):
        self.rows = list(rows)
        self.row = row

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row if self.row is not None else (self.rows[0] if self.rows else None)


class Conn:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if not self.responses:
            return Result()
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def payload(**changes):
    values = dict(
        start_time="08:00", end_time="18:00",
        days=("Monday", "Tuesday"), tariff_name="Business",
        ras_id=None, ports=(ALL,),
    )
    values.update(changes)
    return VoipChargeRuleInput(**values)


def test_create_voip_rule_inserts_native_inherited_row_and_children():
    conn = Conn([
        Result(rows=[(10, "VoIP")]),
        Result(rows=[(3,)]),
        Result(),  # no existing rules for conflict check
        Result(row=(21,)),
        Result(), Result(), Result(), Result(),
    ])
    rule_id = PostgresVoipChargeRuleRepository(conn).create("Calls", payload())
    assert rule_id == 21
    assert any("INSERT INTO voip_charge_rules" in sql for sql, _ in conn.calls)
    assert any("charge_rule_day_of_weeks" in sql for sql, _ in conn.calls)
    assert any("charge_rule_ports" in sql for sql, _ in conn.calls)
    assert conn.calls[-1][1] == (21, ALL)


def test_rule_creation_rejects_non_voip_charge():
    conn = Conn([Result(rows=[(10, "Internet")])])
    with pytest.raises(ChargeTypeError):
        PostgresVoipChargeRuleRepository(conn).create("Internet", payload())


def test_rule_creation_requires_existing_charge_and_tariff():
    with pytest.raises(ChargeNotFound):
        PostgresVoipChargeRuleRepository(Conn([Result()])).create("missing", payload())


def test_rule_time_validation_rejects_cross_midnight_and_empty_days():
    repo = PostgresVoipChargeRuleRepository(Conn([]))
    with pytest.raises(Exception):
        repo._validate(payload(start_time="20:00", end_time="08:00"))
    with pytest.raises(Exception):
        repo._validate(payload(days=()))


def test_source_overlap_guard_checks_same_ras_port_day_and_time():
    conn = Conn([
        Result(rows=[(10, "VoIP")]),
        Result(rows=[(3,)]),
        Result(rows=[(18, time(9), time(17), None)]),
        Result(rows=[(ALL,)]),
        Result(rows=[(0,)]),
    ])
    with pytest.raises(VoipRuleConflictError):
        PostgresVoipChargeRuleRepository(conn).create(
            "Calls", payload(start_time="10:00", end_time="12:00", days=("Monday",))
        )


def test_same_interval_different_ras_is_not_conflict_per_a124():
    conn = Conn([
        Result(rows=[(10, "VoIP")]),
        Result(rows=[(3,)]),
        Result(rows=[(18, time(9), time(17), 4)]),
        Result(row=(21,)),
        Result(), Result(), Result(),
    ])
    assert PostgresVoipChargeRuleRepository(conn).create(
        "Calls", payload(ras_id=None, ports=(ALL,))
    ) == 21
