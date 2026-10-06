from unittest.mock import Mock

from atd_radius.application.radius_runtime import NativeAccountingIdentityResolver, build_radius_dispatcher
from atd_radius.domain.radius import RadiusCode, RadiusPacket


def test_native_identity_resolver_maps_user_and_ras():
    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    ras = Mock()
    ras.get_by_ip.return_value = Mock(ras_id=3)

    resolver = NativeAccountingIdentityResolver(users, ras)

    assert resolver.user_id("alice") == 7
    assert resolver.ras_id("192.0.2.1") == 3


def test_build_radius_dispatcher_uses_native_access_context():
    users = Mock()
    users.get_authentication_record.return_value = (7, "secret", False)
    users.attributes.return_value = []
    dispatcher = build_radius_dispatcher(users)

    response = dispatcher.access(
        RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            4,
            {"User-Name": "alice", "User-Password": "secret"},
            b"0123456789abcdef",
        )
    )

    assert response.code is RadiusCode.ACCESS_ACCEPT
    assert "User-Password" not in response.attributes


def test_runtime_handler_applies_accounting_session():
    from atd_radius.application.radius_runtime import RadiusRuntimeHandler
    from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus
    from atd_radius.domain.radius_dispatch import DispatchResult

    dispatcher = Mock()
    event = AccountingEvent(AccountingStatus.START, "alice", "sid")
    dispatcher.accounting.return_value = DispatchResult(
        RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE, 9, {}, b"0123456789abcdef"), event
    )
    sessions = Mock()
    identities = Mock()
    identities.user_id.return_value = 7
    identities.ras_id.return_value = 3

    handler = RadiusRuntimeHandler(dispatcher, sessions, identities)
    packet = RadiusPacket(RadiusCode.ACCOUNTING_REQUEST, 9, {"Acct-Status-Type": "Start"}, b"0123456789abcdef")

    response = handler(packet, ("192.0.2.1", 1812))

    assert response.code is RadiusCode.ACCOUNTING_RESPONSE
    sessions.apply.assert_called_once_with(event, 7, 3)
