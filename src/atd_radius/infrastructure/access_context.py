"""Native A1.24 Access-Request context enrichment."""
from __future__ import annotations
from typing import Mapping, Protocol
from atd_radius.domain.radius import RadiusPacket
from atd_radius.domain.user_policies import ras_allows_multi_login

class NativeUserSource(Protocol):
    def get_authentication_record(self, username: str) -> tuple[int, str, bool] | None: ...
    def attributes(self, user_id: int) -> list[tuple[str, str]]: ...

class NativeRASSource(Protocol):
    def get_by_ip(self, ip: str): ...
    def attributes(self, ras_id: int) -> list[tuple[str, str]]: ...

class NativeAccessContext:
    """Resolve native users, RAS and native A1.24 RAS-bound IP pools."""
    def __init__(self, users: NativeUserSource, ras: NativeRASSource | None = None) -> None:
        self.users = users
        self.ras = ras

    def enrich(self, packet: RadiusPacket, source_ip: str | None = None) -> Mapping[str, str]:
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
        if self.ras is not None and source_ip:
            ras_record = self.ras.get_by_ip(source_ip)
            if ras_record is not None:
                ras_attrs = {name: value for name, value in self.ras.attributes(ras_record.ras_id)}
                attrs["__ras_multi_login_allowed"] = "1" if ras_allows_multi_login(
                    ras_record.ras_type, ras_attrs, "internet"
                ) else "0"
                if ras_record.ippool_ids:
                    attrs["__ras_ippool_ids"] = ",".join(str(pool_id) for pool_id in ras_record.ippool_ids)
        return attrs
