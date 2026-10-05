from atd_radius.domain.attributes import resolve_attributes


def test_ibsng_scope_precedence_is_deterministic():
    attrs = resolve_attributes(
        {"service-type": "login", "x": "ras"},
        [{"x": "group", "group-only": "1"}],
        [{"x": "service", "service-only": "1"}],
        {"x": "user"},
    )
    assert attrs.get("x") == "user"
    assert attrs.get("group-only") == "1"
    assert attrs.get("service-only") == "1"
    assert attrs.get("service-type") == "login"
