"""Native A1.24 Access-Request context enrichment."""
from __future__ import annotations
from typing import Mapping, Protocol
from atd_radius.domain.radius import RadiusPacket
from atd_radius.domain.radius_auth import (
    RadiusAuthMethod,
    detect_auth_method,
    validate_mschapv2_response,
    verify_chap,
    verify_mschapv1,
    verify_mschapv2,
    derive_mschapv1_mppe_key,
    derive_mschapv2_mppe_keys,
    generate_mschapv2_authenticator_response,
    verify_pap,
)
from atd_radius.domain.user_policies import ras_allows_multi_login
from atd_radius.domain.ras_provider import provider_ip_assignment_for_attributes

class NativeUserSource(Protocol):
    def get_authentication_record(self, username: str) -> tuple[int, str, bool] | None: ...
    def attributes(self, user_id: int) -> list[tuple[str, str]]: ...
    def policy_attributes(self, user_id: int) -> list[tuple[str, str]]: ...

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
        loader = getattr(self.users, "policy_attributes", None)
        if loader is None:
            loader = self.users.attributes
        try:
            loaded_attrs = loader(user_id)
            attrs = {name: value for name, value in loaded_attrs}
        except TypeError:
            attrs = {name: value for name, value in self.users.attributes(user_id)}

        method = detect_auth_method(packet.attributes)
        password_ok = False
        if not locked:
            if method is RadiusAuthMethod.PAP:
                password_ok = verify_pap(str(packet.attributes.get("User-Password", "")), stored_password)
            elif method is RadiusAuthMethod.CHAP:
                password_ok = verify_chap(
                    packet.attributes.get("CHAP-Password"),
                    stored_password,
                    packet.attributes.get("CHAP-Challenge"),
                    packet_authenticator=packet.authenticator,
                )
            elif method is RadiusAuthMethod.MSCHAPV1:
                password_ok = verify_mschapv1(
                    packet.attributes.get("MS-CHAP-Response"),
                    stored_password,
                    packet.attributes.get("MS-CHAP-Challenge"),
                )
                if password_ok:
                    attrs["__mschapv1_mppe_key"] = derive_mschapv1_mppe_key(stored_password).hex()
            elif method is RadiusAuthMethod.MSCHAPV2:
                password_ok = verify_mschapv2(
                    packet.attributes.get("MS-CHAP2-Response"),
                    stored_password,
                    username,
                    packet.attributes.get("MS-CHAP-Challenge"),
                )
                valid_shape = validate_mschapv2_response(
                    packet.attributes.get("MS-CHAP2-Response"),
                    packet.attributes.get("MS-CHAP-Challenge"),
                )
                attrs["__mschapv2_valid_shape"] = "1" if valid_shape else "0"
                if password_ok and valid_shape:
                    response = packet.attributes.get("MS-CHAP2-Response")
                    raw_response = response if isinstance(response, bytes) else bytes.fromhex(str(response))
                    attrs["__mschapv2_success"] = (
                        chr(raw_response[0]) +
                        generate_mschapv2_authenticator_response(
                            stored_password,
                            raw_response[26:50],
                            raw_response[2:18],
                            packet.attributes.get("MS-CHAP-Challenge"),
                            username,
                        )
                    )
                    send_key, recv_key = derive_mschapv2_mppe_keys(
                        stored_password, raw_response[26:50]
                    )
                    attrs["__mschapv2_send_key"] = send_key.hex()
                    attrs["__mschapv2_recv_key"] = recv_key.hex()

        attrs["__user_found"] = "1"
        attrs["__user_id"] = str(user_id)
        attrs["__auth_method"] = method.value
        attrs["__password_ok"] = "1" if password_ok else "0"
        if self.ras is not None and source_ip:
            ras_record = self.ras.get_by_ip(source_ip)
            if ras_record is not None:
                ras_attrs = {name: value for name, value in self.ras.attributes(ras_record.ras_id)}
                attrs["__ras_multi_login_allowed"] = "1" if ras_allows_multi_login(
                    ras_record.ras_type, ras_attrs, "internet"
                ) else "0"
                ip_assignment = provider_ip_assignment_for_attributes(
                    ras_record.ras_type, {**ras_attrs, **packet.attributes}
                )
                if ip_assignment is not None:
                    attrs["__ras_ip_assignment"] = "1" if ip_assignment else "0"
                if ras_record.ippool_ids and ip_assignment is not False:
                    attrs["__ras_ippool_ids"] = ",".join(str(pool_id) for pool_id in ras_record.ippool_ids)
        return attrs
