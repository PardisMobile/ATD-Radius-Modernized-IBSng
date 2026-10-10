from atd_radius.infrastructure.caller_id_mutations import expand_caller_ids


def test_caller_id_expansion_matches_a124_multistr_range_padding():
    assert expand_caller_ids("555{1-3},x{n1-3},ab{l04-05}") == [
        "5551", "5552", "5553", "x1", "x2", "x3", "ab04", "ab05"
    ]


def test_caller_id_expansion_rejects_empty_and_duplicate_values():
    import pytest
    from atd_radius.infrastructure.user_attribute_mutations import UserAttributeMutationError

    with pytest.raises(UserAttributeMutationError):
        expand_caller_ids("")
    with pytest.raises(UserAttributeMutationError):
        expand_caller_ids("101,,102")
    with pytest.raises(UserAttributeMutationError):
        expand_caller_ids("101,101")


def test_caller_id_expansion_rejects_invalid_ranges():
    import pytest
    from atd_radius.infrastructure.user_attribute_mutations import UserAttributeMutationError

    with pytest.raises(UserAttributeMutationError):
        expand_caller_ids("555{3-3}")
