from atd_radius.infrastructure.ibsng_schema_manifest import (
    IBSNG_A124_SEQUENCES,
    IBSNG_A124_TABLES,
    validate_manifest,
)


def test_ibsng_a124_schema_inventory_is_complete():
    validate_manifest()
    assert len(IBSNG_A124_TABLES) == 51
    assert len(IBSNG_A124_SEQUENCES) == 24
    assert "users" in {table.name for table in IBSNG_A124_TABLES}
    assert "user_attrs" in {table.name for table in IBSNG_A124_TABLES}
    assert "internet_charge_rules" in {table.name for table in IBSNG_A124_TABLES}
    assert "voip_charge_rules" in {table.name for table in IBSNG_A124_TABLES}
