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

def test_user_detail_contract_can_hide_independently_unauthorized_reports():
    from atd_radius.api.users import UserComponentsView, UserDetailView

    detail = UserDetailView(
        id=1,
        username="alice",
        locked=False,
        has_password=False,
        groups=[],
        attributes=[],
        components=UserComponentsView(
            normal=None,
            voip=None,
            caller_ids=[],
            persistent_lan=[],
        ),
        connection_logs=None,
        credit_changes=None,
    )
    assert detail.connection_logs is None
    assert detail.credit_changes is None

def test_user_credit_change_contract_uses_two_decimal_precision():
    from decimal import Decimal
    import pytest
    from pydantic import ValidationError
    from atd_radius.api.users import UserCreditChange

    payload = UserCreditChange(delta=Decimal("12.50"), comment="top-up")
    assert payload.delta == Decimal("12.50")
    with pytest.raises(ValidationError):
        UserCreditChange(delta=Decimal("12.501"), comment="invalid precision")


def test_nearest_expiration_uses_effective_absolute_and_relative_attributes():
    from atd_radius.application.online_expiry_loop import nearest_expiration
    epoch, remaining = nearest_expiration(
        {"abs_exp_date": "500", "rel_exp_date": "100", "first_login": "350"},
        now=420,
    )
    assert epoch == 450
    assert remaining == 30


def test_nearest_expiration_uses_group_effective_attribute_when_user_override_is_absent():
    from atd_radius.application.online_expiry_loop import nearest_expiration
    # UserRepository.policy_attributes provides group defaults overridden by user attributes.
    epoch, remaining = nearest_expiration({"abs_exp_date": "700"}, now=400)
    assert epoch == 700
    assert remaining == 300


def test_nearest_expiration_is_absent_without_any_source_deadline():
    from atd_radius.application.online_expiry_loop import nearest_expiration
    assert nearest_expiration({"first_login": "100"}, now=200) == (None, None)
