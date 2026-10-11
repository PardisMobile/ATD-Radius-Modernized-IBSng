from decimal import Decimal

from atd_radius.infrastructure.voip_tariff_repository import PostgresVoipTariffRepository


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class Conn:
    def __init__(self, *, missing=False):
        self.missing = missing
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM voip_charge_rule_tariff" in sql:
            if self.missing:
                return Result([])
            return Result([(4, "International", "legacy tariff")])
        if "FROM tariff_prefix_list" in sql:
            assert params == (4,)
            return Result([
                (10, "98", "Iran", Decimal("60.00"), 10, 3, 30, 20),
                (11, "989", "Mobile", Decimal("90.00"), 5, 2, 6, 12),
            ])
        raise AssertionError(sql)


def test_repository_maps_native_tariff_and_misspelled_source_column():
    conn = Conn()
    tariff = PostgresVoipTariffRepository(conn).get(4)

    assert tariff is not None
    assert tariff.tariff_id == 4
    assert tariff.name == "International"
    assert tariff.comment == "legacy tariff"
    assert len(tariff.prefixes) == 2
    assert tariff.prefixes[0].cpm == Decimal("60.00")
    assert tariff.prefixes[0].min_chargeable_duration == 20
    assert "min_chargable_duration" in conn.calls[1][0]
    assert conn.calls[0][1] == (4,)


def test_repository_uses_longest_prefix_after_loading_native_rows():
    tariff = PostgresVoipTariffRepository(Conn()).get(4)

    assert tariff is not None
    assert tariff.find_prefix("989121255").prefix_id == 11


def test_repository_returns_none_for_unknown_tariff_without_prefix_query():
    conn = Conn(missing=True)

    assert PostgresVoipTariffRepository(conn).get(404) is None
    assert len(conn.calls) == 1


def test_list_loads_tariffs_from_native_tariff_table():
    class MultiConn(Conn):
        def execute(self, sql, params=()):
            self.calls.append((sql, params))
            if "FROM voip_charge_rule_tariff" in sql:
                return Result([(4, "International", ""), (5, "Local", "")])
            if "FROM tariff_prefix_list" in sql:
                return Result([])
            raise AssertionError(sql)

    tariffs = PostgresVoipTariffRepository(MultiConn()).list()
    assert [(item.tariff_id, item.name) for item in tariffs] == [
        (4, "International"),
        (5, "Local"),
    ]
