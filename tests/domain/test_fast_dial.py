from atd_radius.domain.fast_dial import (
    FastDialRuntimeError,
    apply_fast_dial,
    replace_fast_dial_destination,
)


def test_fast_dial_rewrites_redirect_and_records_instance_index():
    instance_attrs = {}
    redirects = []
    result = apply_fast_dial(
        called_number="*72",
        prefix="*",
        destinations=("", "12345", "98765", "", "", "", "", "", "", ""),
        instance_attributes=instance_attrs,
        set_redirect_number=redirects.append,
    )
    assert result == "98765"
    assert instance_attrs == {"fast_dial_index": 2}
    assert redirects == ["98765"]


def test_fast_dial_noops_when_prefix_is_disabled_or_does_not_match():
    attrs = {}
    redirects = []
    for prefix, called in (("", "*2"), ("#", "*2"), ("*", None)):
        assert apply_fast_dial(
            called_number=called,
            prefix=prefix,
            destinations=("",) * 10,
            instance_attributes=attrs,
            set_redirect_number=redirects.append,
        ) is None
    assert attrs == {}
    assert redirects == []


def test_fast_dial_invalid_suffix_and_positive_out_of_range_match_source_error():
    kwargs = {
        "prefix": "*",
        "destinations": ("",) * 10,
        "instance_attributes": {},
        "set_redirect_number": lambda _destination: None,
    }
    try:
        apply_fast_dial(called_number="*abc", **kwargs)
    except FastDialRuntimeError as exc:
        assert "INVALID_FAST_DIAL_INDEX" in str(exc)
    else:
        raise AssertionError("nonnumeric suffix must fail")

    try:
        apply_fast_dial(called_number="*10", **kwargs)
    except FastDialRuntimeError as exc:
        assert "INVALID_FAST_DIAL_INDEX: 10" in str(exc)
    else:
        raise AssertionError("positive out-of-range index must fail")


def test_fast_dial_preserves_python_negative_index_behavior_from_a124():
    attrs = {}
    redirects = []
    assert apply_fast_dial(
        called_number="*-1",
        prefix="*",
        destinations=tuple(str(i) for i in range(10)),
        instance_attributes=attrs,
        set_redirect_number=redirects.append,
    ) == "9"
    assert attrs["fast_dial_index"] == -1
    assert redirects == ["9"]


def test_actions_manager_slot_update_requires_digit_destination_and_index_0_to_9():
    original = ("",) * 10
    updated = replace_fast_dial_destination(original, 3, "123456")
    assert updated[3] == "123456"
    assert updated[:3] == ("", "", "")
    assert updated[4:] == ("",) * 6

    for index, destination in ((10, "123"), (-1, "123"), (0, "12x")):
        try:
            replace_fast_dial_destination(original, index, destination)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid destination/index must fail")
