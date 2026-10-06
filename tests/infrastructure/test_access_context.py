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
    response = peer_challenge + b"\x00" * 8 + nt_response + b"\x00"
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
