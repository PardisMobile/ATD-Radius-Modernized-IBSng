from __future__ import annotations

from atd_radius.api.groups import GroupAttributePayload
from atd_radius.api.ras import RASPortPayload


def test_group_attribute_update_uses_explicit_body_payload():
    payload = GroupAttributePayload(attr_value="10")
    assert payload.attr_value == "10"


def test_ras_port_payload_keeps_port_identity_and_fields():
    payload = RASPortPayload(
        port_name="17",
        phone="123",
        type="async",
        comment="test",
    )
    assert payload.port_name == "17"
    assert payload.phone == "123"
    assert payload.type == "async"
    assert payload.comment == "test"
