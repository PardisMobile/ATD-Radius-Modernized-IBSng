from atd_radius.infrastructure.attribute_repository import InMemoryAttributeRepository, StoredAttribute


def test_attribute_repository_preserves_unknown_and_multiple_values():
    repo = InMemoryAttributeRepository()
    repo.replace_for_owner(
        "user",
        7,
        [
            StoredAttribute("user", 7, "custom_ibsng_attr", "one", 0),
            StoredAttribute("user", 7, "custom_ibsng_attr", "two", 1),
        ],
    )
    values = repo.list_for_owner("user", 7)
    assert [item.value for item in values] == ["one", "two"]
    assert values[0].name == "custom_ibsng_attr"
