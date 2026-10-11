from decimal import Decimal

import pytest

from atd_radius.infrastructure.voip_tariff_repository import (
    PostgresVoipTariffRepository,
    PrefixConflictError,
    PrefixInput,
    PrefixInputError,
    PrefixNotFound,
    TariffAlreadyExists,
    TariffInUseError,
)


class Result:
    def __init__(self, rows=(), row=None):
        self.rows = list(rows)
        self.row = row

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if self.row is not None:
            return self.row
        return self.rows[0] if self.rows else None


class ScriptedConn:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if self.answers:
            answer = self.answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        return Result()


def prefix(code="98"):
    return PrefixInput(code, "Iran", Decimal("60.00"), 10, 3, 30, 20)


def test_create_tariff_uses_native_table_and_sequence_with_parameterized_values():
    conn = ScriptedConn([Result(row=None), Result(row=(15,)), Result()])
    tariff_id = PostgresVoipTariffRepository(conn).create_tariff("New_Tariff-1", "note")
    assert tariff_id == 15
    assert "LOCK TABLE voip_charge_rule_tariff" in conn.calls[0][0]
    assert "nextval('voip_charge_rule_tariff_tariff_id_seq')" in conn.calls[2][0]
    assert conn.calls[3][1] == (15, "New_Tariff-1", "note")


def test_create_tariff_rejects_duplicate_name_before_insert():
    conn = ScriptedConn([Result(), Result(row=(3,))])
    with pytest.raises(TariffAlreadyExists):
        PostgresVoipTariffRepository(conn).create_tariff("existing", "")
    assert not any("INSERT INTO voip_charge_rule_tariff" in sql for sql, _ in conn.calls)


def test_delete_tariff_refuses_tariff_referenced_by_voip_charge_rule():
    conn = ScriptedConn([Result(), Result(row=(7,)), Result(row=(21,))])
    with pytest.raises(TariffInUseError):
        PostgresVoipTariffRepository(conn).delete_tariff("used")
    assert not any("DELETE FROM" in sql for sql, _ in conn.calls)


def test_add_prefix_uses_native_misspelled_column_and_checks_duplicates():
    conn = ScriptedConn([
        Result(row=(7,)),
        Result(rows=[("90",)]),
        Result(row=(42,)),
        Result(),
    ])
    ids = PostgresVoipTariffRepository(conn).add_prefixes("tariff", [prefix("98")])
    assert ids == [42]
    insert_sql, params = conn.calls[-1]
    assert "min_chargable_duration" in insert_sql
    assert params == (7, 42, "98", "Iran", Decimal("60.00"), 10, 3, 30, 20)


def test_add_prefix_rejects_duplicate_and_non_digit_code():
    duplicate_conn = ScriptedConn([Result(row=(7,)), Result(rows=[("98",)])])
    with pytest.raises(PrefixConflictError):
        PostgresVoipTariffRepository(duplicate_conn).add_prefixes("tariff", [prefix("98")])

    bad_conn = ScriptedConn([Result(row=(7,)), Result(rows=[])])
    with pytest.raises(PrefixInputError):
        PostgresVoipTariffRepository(bad_conn).add_prefixes(
            "tariff", [PrefixInput("9A", "bad", Decimal("1"), 0, 0, 0, 0)]
        )


def test_update_prefix_requires_prefix_to_belong_to_tariff():
    conn = ScriptedConn([Result(row=(7,)), Result(row=(8, "98"))])
    with pytest.raises(PrefixNotFound):
        PostgresVoipTariffRepository(conn).update_prefix("tariff", 11, prefix())


def test_delete_prefixes_requires_every_requested_code_to_exist():
    conn = ScriptedConn([Result(row=(7,)), Result(rows=[("98",)])])
    with pytest.raises(PrefixNotFound):
        PostgresVoipTariffRepository(conn).delete_prefixes("tariff", ["98", "99"])


def test_delete_prefixes_rejects_empty_input():
    with pytest.raises(PrefixInputError):
        PostgresVoipTariffRepository(ScriptedConn([])).delete_prefixes("tariff", [])
