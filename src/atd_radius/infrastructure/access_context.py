"""Native A1.24 Access-Request context enrichment."""
from __future__ import annotations
from typing import Mapping, Protocol
from atd_radius.domain.radius import RadiusPacket

class NativeUserSource(Protocol):
    def get_authentication_record(self, username: str) -> tuple[int, str, bool] | None: ...
    def attributes(self, user_id: int) -> list[tuple[str, str]]: ...

class NativeAccessContext:
    """Resolve native users and user_attrs for an Access-Request.

    normal_users.normal_password is intentionally compared as stored because
    that is the native A1.24 persistence contract; Argon2 is not substituted
    for the legacy credential field.
    """
    def __init__(self, users: NativeUserSource) -> None:
        self.users = users

    def enrich(self, packet: RadiusPacket) -> Mapping[str, str]:
        username = packet.attributes.get("User-Name", "")
        record = self.users.get_authentication_record(username)
        if record is None:
            return {"__user_found": "0", "__password_ok": "0"}
        user_id, stored_password, locked = record
        attrs = {name: value for name, value in self.users.attributes(user_id)}
        attrs["__user_found"] = "1"
        attrs["__user_id"] = str(user_id)
        attrs["__password_ok"] = "1" if (
            not locked and packet.attributes.get("User-Password", "") == stored_password
        ) else "0"
        return attrs
