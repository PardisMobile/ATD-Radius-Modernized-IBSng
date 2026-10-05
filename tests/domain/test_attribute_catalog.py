from atd_radius.domain.attribute_catalog import (
    ATTRIBUTE_DEFINITIONS,
    get_attribute_spec,
    get_ibsng_attribute_definitions,
)
from atd_radius.domain.attributes import AttributeOperator


def test_catalog_is_machine_readable_and_stable():
    definitions = get_ibsng_attribute_definitions()
    assert definitions == ATTRIBUTE_DEFINITIONS
    assert "session_timeout" in definitions
    assert "ippool" in definitions
    assert "radius_attrs" in definitions


def test_multivalue_attributes_keep_merge_operators_explicit():
    radius_attrs = get_attribute_spec("radius_attrs").definition
    caller_id = get_attribute_spec("caller_id").definition
    assert radius_attrs.multi is True
    assert caller_id.multi is True
    assert AttributeOperator.ADD in radius_attrs.operators
    assert AttributeOperator.REMOVE in radius_attrs.operators


def test_session_attributes_expose_explicit_radius_mapping():
    assert get_attribute_spec("session_timeout").radius_name == "Session-Timeout"
    assert get_attribute_spec("idle_timeout").radius_name == "Idle-Timeout"


def test_unknown_attribute_fails_loudly():
    try:
        get_attribute_spec("definitely_not_an_ibsng_attribute")
    except KeyError as exc:
        assert "not catalogued" in str(exc)
    else:
        raise AssertionError("unknown attributes must not silently enter the catalog")
