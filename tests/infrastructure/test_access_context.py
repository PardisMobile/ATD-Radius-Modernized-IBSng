from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.infrastructure.access_context import NativeAccessContext

class FakeUsers:
    def __init__(self):
        self.records = {"alice": (7, "secret", False), "locked": (8, "secret", True)}
        self.attrs = {7: [("multi_login", "2"), ("session_timeout", "60")], 8: []}

    def get_authentication_record(self, username):
        return self.records.get(username)

    def attributes(self, user_id):
        return self.attrs.get(user_id, [])

def test_native_access_context_authenticates_native_password():
    ctx = NativeAccessContext(FakeUsers())
    packet = RadiusPacket(RadiusCode.ACCESS_REQUEST, 1, {"User-Name": "alice", "User-Password": "secret"})
    attrs = ctx.enrich(packet)
    assert attrs["__user_found"] == "1"
    assert attrs["__password_ok"] == "1"
    assert attrs["multi_login"] == "2"

def test_native_access_context_rejects_wrong_password():
    ctx = NativeAccessContext(FakeUsers())
    packet = RadiusPacket(RadiusCode.ACCESS_REQUEST, 1, {"User-Name": "alice", "User-Password": "wrong"})
    assert ctx.enrich(packet)["__password_ok"] == "0"

def test_native_access_context_rejects_locked_user():
    ctx = NativeAccessContext(FakeUsers())
    packet = RadiusPacket(RadiusCode.ACCESS_REQUEST, 1, {"User-Name": "locked", "User-Password": "secret"})
    assert ctx.enrich(packet)["__password_ok"] == "0"

def test_native_access_context_marks_unknown_user():
    ctx = NativeAccessContext(FakeUsers())
    packet = RadiusPacket(RadiusCode.ACCESS_REQUEST, 1, {"User-Name": "missing", "User-Password": "secret"})
    assert ctx.enrich(packet) == {"__user_found": "0", "__password_ok": "0"}


def test_native_access_context_prefers_effective_group_policy_attributes():
    class EffectiveUsers(FakeUsers):
        def policy_attributes(self, user_id):
            return [("multi_login", "3"), ("session_timeout", "120"), ("group_only", "yes")]

    ctx = NativeAccessContext(EffectiveUsers())
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        2,
        {"User-Name": "alice", "User-Password": "secret"},
    )
    attrs = ctx.enrich(packet)
    assert attrs["multi_login"] == "3"
    assert attrs["session_timeout"] == "120"
    assert attrs["group_only"] == "yes"


def test_native_access_context_authenticates_mschapv2():
    class MSCHAPUsers(FakeUsers):
        def __init__(self):
            self.records = {"User": (9, "clientPass", False)}
            self.attrs = {9: []}

    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    response = b"\x01\x00" + peer_challenge + b"\x00" * 8 + nt_response
    ctx = NativeAccessContext(MSCHAPUsers())
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        3,
        {
            "User-Name": "User",
            "MS-CHAP-Challenge": auth_challenge,
            "MS-CHAP2-Response": response,
        },
    )
    attrs = ctx.enrich(packet)
    assert attrs["__auth_method"] == "mschapv2"
    assert attrs["__mschapv2_valid_shape"] == "1"
    assert attrs["__password_ok"] == "1"


def test_native_access_context_emits_mschapv2_success():
    class MSCHAPUsers(FakeUsers):
        def __init__(self):
            self.records = {"User": (9, "clientPass", False)}
            self.attrs = {9: []}

    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    response = b"\x01\x00" + peer_challenge + b"\x00" * 8 + nt_response
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        4,
        {
            "User-Name": "User",
            "MS-CHAP-Challenge": auth_challenge,
            "MS-CHAP2-Response": response,
        },
    )
    attrs = NativeAccessContext(MSCHAPUsers()).enrich(packet)
    assert attrs["__mschapv2_success"] == b"\x01S=407A5589115FD0D6209F510FE9C04566932CDA56"



def test_mschapv2_uses_canonical_normal_username_for_source_hashes():
    from atd_radius.domain.radius_auth import _challenge_hash, _nt_response

    class CanonicalMSCHAPUsers(FakeUsers):
        def __init__(self):
            self.records = {"alias": (9, "clientPass", False)}
            self.attrs = {9: []}

        def normal_credentials(self, user_id):
            assert user_id == 9
            return ("StoredUser", "clientPass")

    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = _nt_response(
        _challenge_hash(peer_challenge, auth_challenge, "StoredUser"),
        "clientPass",
    )
    response = b"\x01\x00" + peer_challenge + b"\x00" * 8 + nt_response
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        5,
        {
            "User-Name": "alias",
            "MS-CHAP-Challenge": auth_challenge,
            "MS-CHAP2-Response": response,
        },
    )

    attrs = NativeAccessContext(CanonicalMSCHAPUsers()).enrich(packet)
    assert attrs["__password_ok"] == "1"
    assert attrs["__mschapv2_success"].startswith(b"\x01S=")

def test_native_access_context_maps_mikrotik_station_ip_for_limit_plugin():
    class RestrictedUsers(FakeUsers):
        def __init__(self):
            super().__init__()
            self.attrs[7] = [("limit_station_ip", "192.0.2.0/24")]

    class RASRecord:
        ras_id = 3
        ras_type = "Mikrotik"
        ippool_ids = ()

        def all_attributes(self):
            return {}

    class RAS:
        def get_by_ip(self, source_ip):
            assert source_ip == "192.0.2.1"
            return RASRecord()

    ctx = NativeAccessContext(RestrictedUsers(), RAS())
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        8,
        {
            "User-Name": "alice",
            "User-Password": "secret",
            "NAS-Port-Type": "Virtual",
            "Calling-Station-Id": "192.0.2.25",
        },
    )

    attrs = ctx.enrich(packet, "192.0.2.1")

    assert attrs["station_ip"] == "192.0.2.25"
    assert attrs["limit_station_ip"] == "192.0.2.0/24"
    assert attrs["__ras_id"] == "3"



def test_native_dispatcher_completes_chap_using_request_authenticator():
    from hashlib import md5
    from atd_radius.application.radius_runtime import build_radius_dispatcher
    from atd_radius.domain.radius import RadiusCode

    identifier = b"\x09"
    authenticator = bytes(range(16))
    challenge_response = identifier + md5(identifier + b"secret" + authenticator).digest()
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        9,
        {"User-Name": "alice", "CHAP-Password": challenge_response},
        authenticator,
    )

    response = build_radius_dispatcher(FakeUsers()).access(packet, source_ip=None)

    assert response.code is RadiusCode.ACCESS_ACCEPT
    assert response.identifier == packet.identifier
    assert "CHAP-Password" not in response.attributes
    assert not any(str(key).startswith("__") for key in response.attributes)


def test_native_dispatcher_completes_mschapv1_and_emits_mppe_material():
    from atd_radius.application.radius_runtime import build_radius_dispatcher
    from atd_radius.domain.radius import RadiusCode

    class MSCHAPUsers(FakeUsers):
        def __init__(self):
            self.records = {"User": (9, "clientPass", False)}
            self.attrs = {9: []}

    challenge = bytes.fromhex("5B5D7C7D7B3F2F3E")
    nt_response = bytes.fromhex("9F9BEC2D4EA5BD51E59EC761C102526860A6C4DE36AFB512")
    response_value = b"\x01\x00" + b"\x00" * 16 + b"\x00" * 8 + nt_response
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        10,
        {
            "User-Name": "User",
            "MS-CHAP-Challenge": challenge,
            "MS-CHAP-Response": response_value,
        },
    )

    response = build_radius_dispatcher(MSCHAPUsers()).access(packet)

    assert response.code is RadiusCode.ACCESS_ACCEPT
    assert len(response.attributes["MS-CHAP-MPPE-Keys"]) == 64
    assert response.attributes["MS-MPPE-Encryption-Policy"] == "00000001"
    assert response.attributes["MS-MPPE-Encryption-Types"] == "00000006"
    assert not any(str(key).startswith("__") for key in response.attributes)


def test_native_dispatcher_completes_mschapv2_for_supported_codec_shapes():
    from atd_radius.application.radius_runtime import build_radius_dispatcher
    from atd_radius.domain.radius import RadiusCode

    class MSCHAPUsers(FakeUsers):
        def __init__(self):
            self.records = {"User": (9, "clientPass", False)}
            self.attrs = {9: []}

    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    response_bytes = b"\x01\x00" + peer_challenge + b"\x00" * 8 + nt_response

    # The actual UDP codec yields bytes; adapter-level fixtures sometimes use
    # bytearray or canonical hexadecimal text. All three must produce the same
    # authenticator response and the same server-side MPPE keys.
    for response_value in (response_bytes, bytearray(response_bytes), response_bytes.hex()):
        packet = RadiusPacket(
            RadiusCode.ACCESS_REQUEST,
            11,
            {
                "User-Name": "User",
                "MS-CHAP-Challenge": auth_challenge,
                "MS-CHAP2-Response": response_value,
            },
        )
        response = build_radius_dispatcher(MSCHAPUsers()).access(packet)

        assert response.code is RadiusCode.ACCESS_ACCEPT
        assert response.attributes["MS-CHAP2-Success"] == (
            b"\x01S=407A5589115FD0D6209F510FE9C04566932CDA56"
        )
        assert response.attributes["MS-MPPE-Send-Key"] == "8b7cdc149b993a1ba118cb153f56dccb"
        assert response.attributes["MS-MPPE-Recv-Key"] == "d5f0e9521e3ea9589645e86051c82226"
        assert response.attributes["MS-MPPE-Encryption-Policy"] == "00000001"
        assert response.attributes["MS-MPPE-Encryption-Types"] == "00000006"
        assert not any(str(key).startswith("__") for key in response.attributes)


def test_native_dispatcher_rejects_bad_mschapv2_without_leaking_mppe_keys():
    from atd_radius.application.radius_runtime import build_radius_dispatcher
    from atd_radius.domain.radius import RadiusCode

    class MSCHAPUsers(FakeUsers):
        def __init__(self):
            self.records = {"User": (9, "clientPass", False)}
            self.attrs = {9: []}

    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    wrong_nt_response = b"\x00" * 24
    response_value = b"\x01\x00" + peer_challenge + b"\x00" * 8 + wrong_nt_response
    packet = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        12,
        {
            "User-Name": "User",
            "MS-CHAP-Challenge": auth_challenge,
            "MS-CHAP2-Response": response_value,
        },
    )

    response = build_radius_dispatcher(MSCHAPUsers()).access(packet)

    assert response.code is RadiusCode.ACCESS_REJECT
    assert "MS-MPPE-Send-Key" not in response.attributes
    assert "MS-MPPE-Recv-Key" not in response.attributes
    assert "MS-CHAP2-Success" not in response.attributes


def test_mschapv2_native_authentication_survives_radius_wire_and_mppe_round_trip():
    from atd_radius.application.radius_runtime import build_radius_dispatcher
    from atd_radius.domain.radius import RadiusCode
    from atd_radius.domain.radius_codec import decode, encode, encode_response

    class MSCHAPUsers(FakeUsers):
        def __init__(self):
            self.records = {"User": (9, "clientPass", False)}
            self.attrs = {9: []}

    secret = "shared"
    auth_challenge = bytes.fromhex("5B5D7C7D7B3F2F3E3C2C602132262628")
    peer_challenge = bytes.fromhex("21402324255E262A28295F2B3A337C7E")
    nt_response = bytes.fromhex("82309ECD8D708B5EA08FAA3981CD83544233114A3D85D6DF")
    authenticator = bytes.fromhex("00112233445566778899aabbccddeeff")
    original_request = RadiusPacket(
        RadiusCode.ACCESS_REQUEST,
        13,
        {
            "User-Name": "User",
            "MS-CHAP-Challenge": auth_challenge,
            "MS-CHAP2-Response": (
                b"\x01\x00" + peer_challenge + b"\x00" * 8 + nt_response
            ),
        },
        authenticator,
    )

    # Exercise the same binary codec and response-signing path used by UDP.
    wire_request = encode(original_request, secret)
    decoded_request = decode(wire_request, secret)
    logical_response = build_radius_dispatcher(MSCHAPUsers()).access(decoded_request)
    assert logical_response.code is RadiusCode.ACCESS_ACCEPT
    wire_response = encode_response(logical_response, decoded_request, secret)
    decoded_response = decode(
        wire_response,
        secret,
        request_authenticator=decoded_request.authenticator,
    )

    assert decoded_response.code is RadiusCode.ACCESS_ACCEPT
    assert decoded_response.identifier == original_request.identifier
    assert decoded_response.attributes["MS-CHAP2-Success"] == (
        "\\x01S=407A5589115FD0D6209F510FE9C04566932CDA56"
    )
    assert decoded_response.attributes["MS-MPPE-Send-Key"] == "8b7cdc149b993a1ba118cb153f56dccb"
    assert decoded_response.attributes["MS-MPPE-Recv-Key"] == "d5f0e9521e3ea9589645e86051c82226"
