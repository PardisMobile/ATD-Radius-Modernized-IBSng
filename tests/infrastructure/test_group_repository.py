from __future__ import annotations

from atd_radius.infrastructure.group import GroupRepository


def test_group_name_validation_matches_a124_name_charset() -> None:
    GroupRepository._validate_name("group_01-test")
    for value in ("", "group name", "گروه"):
        try:
            GroupRepository._validate_name(value)
        except ValueError:
            continue
        raise AssertionError(value)


def test_group_record_mapping() -> None:
    record = GroupRepository._record((7, "test_group", 2, "comment"))
    assert record.id == 7
    assert record.name == "test_group"
    assert record.owner_id == 2
    assert record.comment == "comment"
