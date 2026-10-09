from __future__ import annotations

from atd_radius.api.groups import GroupAttributePayload
from atd_radius.api.ras import RASInfo, RASListView, RASPortPayload


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


def test_user_native_component_contract_never_contains_password_field():
    from atd_radius.api.users import NativeCredentialView, UserComponentsView
    normal = NativeCredentialView(username="alice", has_password=True)
    view = UserComponentsView(normal=normal, voip=None, caller_ids=["0912"], persistent_lan=[])
    assert view.normal.username == "alice"
    assert view.normal.has_password is True
    assert "password" not in view.normal.model_fields


def test_user_component_contract_covers_voip_without_password():
    from atd_radius.api.users import NativeCredentialView, UserComponentsView
    view = UserComponentsView(
        normal=NativeCredentialView(username="alice", has_password=True),
        voip=NativeCredentialView(username="1001", has_password=True),
        caller_ids=[], persistent_lan=[],
    )
    assert view.voip.username == "1001"
    assert view.voip.has_password is True
    assert "password" not in view.voip.model_fields


def test_ras_list_contract_does_not_expose_radius_secret():
    assert "radius_secret" not in RASListView.model_fields
    assert "radius_secret" in RASInfo.model_fields
