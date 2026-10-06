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
