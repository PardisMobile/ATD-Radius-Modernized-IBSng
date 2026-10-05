from atd_radius.domain.attributes import (
    AttributeDefinition,
    AttributeOperator,
    AttributeScope,
    AttributeValue,
    resolve_typed_attributes,
)


def test_user_overrides_group_and_service_for_scalar_value():
    definitions = {"Session-Timeout": AttributeDefinition("Session-Timeout", "integer")}
    result = resolve_typed_attributes(
        definitions,
        [
            [AttributeValue("Session-Timeout", 3600, AttributeScope.RAS)],
            [AttributeValue("Session-Timeout", 1800, AttributeScope.GROUP)],
            [AttributeValue("Session-Timeout", 900, AttributeScope.USER)],
        ],
    )
    assert result.get("Session-Timeout") == 900
    assert [x.scope for x in result.explain("Session-Timeout")] == [
        AttributeScope.RAS,
        AttributeScope.GROUP,
        AttributeScope.USER,
    ]


def test_multivalue_add_and_remove_are_deterministic():
    definitions = {
        "Reply-Group": AttributeDefinition(
            "Reply-Group", multi=True,
            operators=(AttributeOperator.SET, AttributeOperator.ADD, AttributeOperator.REMOVE),
        )
    }
    result = resolve_typed_attributes(
        definitions,
        [
            [AttributeValue("Reply-Group", "basic", AttributeScope.GROUP)],
            [AttributeValue("Reply-Group", "premium", AttributeScope.SERVICE, operator=AttributeOperator.ADD)],
            [AttributeValue("Reply-Group", "basic", AttributeScope.USER, operator=AttributeOperator.REMOVE)],
        ],
    )
    assert result.get("Reply-Group") == ["premium"]


def test_boolean_coercion():
    definitions = {"Simultaneous-Use": AttributeDefinition("Simultaneous-Use", "boolean")}
    result = resolve_typed_attributes(
        definitions,
        [[AttributeValue("Simultaneous-Use", "false", AttributeScope.USER)]],
    )
    assert result.get("Simultaneous-Use") is False
