import pytest

from atd_radius.infrastructure.charges import (
    ChargeAlreadyExists,
    ChargeInUseError,
    ChargeInputError,
    ChargeNotFound,
    PostgresChargeRepository,
)


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)
    def fetchall(self):
        return self.rows
    def fetchone(self):
        return self.rows[0] if self.rows else None


class Conn:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if not self.responses:
            return Result()
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_create_charge_uses_native_sequence_and_fields():
    conn = Conn([Result(), Result(), Result([(12,)]), Result()])
    charge_id = PostgresChargeRepository(conn).create(
        "broadband_1", "comment", "Internet", 7, True
    )
    assert charge_id == 12
    assert "nextval('charges_id_seq')" in conn.calls[2][0]
    assert "INSERT INTO charges" in conn.calls[3][0]
    assert conn.calls[3][1] == (12, "broadband_1", "comment", "Internet", 7, True)


def test_create_charge_rejects_duplicate_name_and_invalid_type():
    repo = PostgresChargeRepository(Conn([Result(), Result([(2,)])]))
    with pytest.raises(ChargeAlreadyExists):
        repo.create("existing", "", "Internet", 7, False)
    with pytest.raises(ChargeInputError):
        repo._validate("bad name", "Internet")
    with pytest.raises(ChargeInputError):
        repo._validate("valid_name", "VoIP-ish")


def test_update_charge_preserves_type_and_owner_fields():
    conn = Conn([Result([(9,)]), Result(), Result()])
    PostgresChargeRepository(conn).update(9, "renamed", "new", True)
    sql, params = conn.calls[-1]
    assert "UPDATE charges SET name=%s, comment=%s, visible_to_all=%s" in sql
    assert params == ("renamed", "new", True, 9)


def test_delete_charge_blocks_users_or_groups_that_reference_it():
    conn = Conn([
        Result(), Result([(12, "Internet")]),
        Result([(3,)]), Result([]),
    ])
    with pytest.raises(ChargeInUseError, match="users=3"):
        PostgresChargeRepository(conn).delete("broadband")
    assert not any("DELETE FROM charges" in sql for sql, _ in conn.calls)


def test_delete_charge_removes_native_rules_and_child_rows_before_charge():
    conn = Conn([
        Result(), Result([(12, "Internet")]),
        Result([]), Result([]), Result([(20,)]),
        Result(), Result(), Result(), Result(),
    ])
    charge_id = PostgresChargeRepository(conn).delete("broadband")
    assert charge_id == 12
    statements = [sql for sql, _ in conn.calls]
    charge_delete = next(i for i, sql in enumerate(statements) if "DELETE FROM charges" in sql)
    assert statements.index("DELETE FROM charge_rule_ports WHERE charge_rule_id=%s") < charge_delete
    assert statements.index("DELETE FROM charge_rule_day_of_weeks WHERE charge_rule_id=%s") < charge_delete
    assert any("DELETE FROM internet_charge_rules" in sql for sql in statements)


def test_delete_charge_raises_not_found_without_side_effects():
    conn = Conn([Result(), Result([])])
    with pytest.raises(ChargeNotFound):
        PostgresChargeRepository(conn).delete("missing")
    assert not any("DELETE FROM" in sql for sql, _ in conn.calls)
