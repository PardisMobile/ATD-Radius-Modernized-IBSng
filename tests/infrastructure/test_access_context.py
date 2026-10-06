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
