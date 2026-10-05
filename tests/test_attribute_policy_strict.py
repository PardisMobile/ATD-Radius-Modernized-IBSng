from atd_radius.domain.attributes import (
    AttributeDefinition,
    AttributeOperator,
    AttributeScope,
    AttributeValidationError,
    AttributeValue,
    resolve_typed_attributes,
)


def test_add_and_remove_require_multivalue_definition():
    definitions = {"session_timeout": AttributeDefinition("session_timeout", "integer")}
    with __import__("pytest").raises(AttributeValidationError):
        resolve_typed_attributes(definitions, [[AttributeValue(
            "session_timeout", 60, AttributeScope.USER, operator=AttributeOperator.ADD
        )]])
    with __import__("pytest").raises(AttributeValidationError):
        resolve_typed_attributes(definitions, [[AttributeValue(
            "session_timeout", 60, AttributeScope.USER, operator=AttributeOperator.REMOVE
        )]])


def test_multi_value_remove_is_deterministic():
    definitions = {
        "radius_attrs": AttributeDefinition(
            "radius_attrs", "string", multi=True,
            operators=(AttributeOperator.SET, AttributeOperator.ADD, AttributeOperator.REMOVE),
        )
    }
    result = resolve_typed_attributes(definitions, [[
        AttributeValue("radius_attrs", "A", AttributeScope.GROUP, operator=AttributeOperator.ADD),
        AttributeValue("radius_attrs", "B", AttributeScope.GROUP, operator=AttributeOperator.ADD),
        AttributeValue("radius_attrs", "A", AttributeScope.USER, operator=AttributeOperator.REMOVE),
    ]])
    assert result.values["radius_attrs"] == ["B"]
