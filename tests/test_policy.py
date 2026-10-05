from atd_radius.domain.policy import effective_attributes


def test_attribute_precedence():
    assert effective_attributes({"x": "ras"}, {"x": "group"}, {"x": "user"})["x"] == "user"
