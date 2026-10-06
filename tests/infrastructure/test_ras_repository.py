from __future__ import annotations

from atd_radius.infrastructure.ras import RASRepository


def test_ras_record_mapping_preserves_native_columns() -> None:
    record = RASRepository._ras((3, "router", "192.0.2.10", "Mikrotik", "secret", True, "test"))
    assert record.ras_id == 3
    assert record.description == "router"
    assert record.ip == "192.0.2.10"
    assert record.ras_type == "Mikrotik"
    assert record.radius_secret == "secret"
    assert record.active is True
    assert record.comment == "test"
