from atd_radius.domain.attribute_catalog import get_ibsng_attribute_definitions
from atd_radius.domain.attributes import AttributeOperator, AttributeScope, AttributeValue, resolve_typed_attributes


def test_catalog_contains_source_evidenced_policy_attributes():
    catalog = get_ibsng_attribute_definitions()
    for name in (
        "multi_login",
        "ippool",
        "assign_ip",
        "limit_mac",
        "limit_station_ip",
        "session_timeout",
        "idle_timeout",
        "limit_caller_id",
        "save_bw_usage",
        "persistent_lan_ip",
        "voip_preferred_language",
    ):
        assert name in catalog


def test_catalog_drives_typed_resolution_and_provenance():
    catalog = get_ibsng_attribute_definitions()
    result = resolve_typed_attributes(
        catalog,
        [
            [AttributeValue("session_timeout", "3600", AttributeScope.GROUP, source_id="group:1")],
            [AttributeValue("session_timeout", "1800", AttributeScope.USER, source_id="user:1")],
        ],
    )
    assert result.get("session_timeout") == 1800
    assert [item.source_id for item in result.explain("session_timeout")] == ["group:1", "user:1"]


def test_multivalue_radius_attributes_merge():
    catalog = get_ibsng_attribute_definitions()
    result = resolve_typed_attributes(
        catalog,
        [
            [AttributeValue("radius_attrs", "Mikrotik-Rate-Limit=10M", AttributeScope.GROUP)],
            [AttributeValue("radius_attrs", "Session-Timeout=3600", AttributeScope.USER, operator=AttributeOperator.ADD)],
        ],
    )
    assert result.get("radius_attrs") == ["Mikrotik-Rate-Limit=10M", "Session-Timeout=3600"]
