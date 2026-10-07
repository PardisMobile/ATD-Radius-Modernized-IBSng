"""Source-derived A1.24 RAS provider profiles.

Profiles describe provider-specific identity and explicit capability facts.
They are metadata for adapters; they do not replace the canonical source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RASProviderProfile:
    name: str
    unique_id: str | None = None
    internet_multi_login: bool | None = None
    voip_multi_login: bool | None = None
    ip_assignment: bool | None = None
    accounting_statuses: tuple[str, ...] = ("Start", "Stop", "Alive")
    disconnect_strategy: str | None = None


_PROFILES: tuple[RASProviderProfile, ...] = (
    RASProviderProfile("asterisk", unique_id="h323_conf_id", voip_multi_login=False),
    RASProviderProfile("bsae", unique_id="port", internet_multi_login=False),
    RASProviderProfile("chilli_spot", unique_id="port", ip_assignment=False, accounting_statuses=("Start", "Stop"), disconnect_strategy="provider-port"),
    RASProviderProfile("cisco", unique_id="port", internet_multi_login=False, voip_multi_login=False, disconnect_strategy="snmp-or-rsh"),
    RASProviderProfile("cisco_vpdn", unique_id="acct_session_id", disconnect_strategy="rsh-interface"),
    RASProviderProfile("gnugk", unique_id="h323_conf_id", voip_multi_login=False),
    RASProviderProfile("mikrotik", unique_id="port", disconnect_strategy="rsh-port"),
    RASProviderProfile("mvts", unique_id="h323_conf_id"),
    RASProviderProfile("plan", unique_id="mac_ip", ip_assignment=False),
    RASProviderProfile("portmaster", unique_id="port", disconnect_strategy="snmp-port"),
    RASProviderProfile("portslave", unique_id="port", disconnect_strategy="launcher"),
    RASProviderProfile("pppd", unique_id="port"),
    RASProviderProfile("ser", unique_id="call_id"),
    RASProviderProfile("tenor", unique_id="h323_conf_id", internet_multi_login=False, voip_multi_login=False, disconnect_strategy="h323-cause"),
    RASProviderProfile("total_control", unique_id="interface_index", disconnect_strategy="snmp-interface"),
)

_ALIASES = {
    "chillispot": "chilli_spot",
    "chilli spot": "chilli_spot",
    "cisco vpdn": "cisco_vpdn",
    "gnugk": "gnugk",
    "gnu gk": "gnugk",
    "quintum tenor": "tenor",
    "persistent lan": "plan",
    "persistent_lan": "plan",
    "port master": "portmaster",
    "port slave": "portslave",
    "total control": "total_control",
}


def normalize_ras_type(ras_type: str | None) -> str:
    key = (ras_type or "").strip().lower()
    return _ALIASES.get(key, key.replace("-", "_").replace(" ", "_"))


def provider_profile(ras_type: str | None) -> RASProviderProfile | None:
    key = normalize_ras_type(ras_type)
    return next((profile for profile in _PROFILES if profile.name == key), None)


def provider_unique_id(ras_type: str | None) -> str | None:
    profile = provider_profile(ras_type)
    return profile.unique_id if profile else None


def provider_multi_login(ras_type: str | None, service: str = "internet") -> bool | None:
    profile = provider_profile(ras_type)
    if profile is None:
        return None
    return profile.voip_multi_login if service == "voip" else profile.internet_multi_login


def provider_ip_assignment(ras_type: str | None) -> bool | None:
    profile = provider_profile(ras_type)
    return profile.ip_assignment if profile else None


def provider_supports_status(ras_type: str | None, status: str) -> bool:
    profile = provider_profile(ras_type)
    return profile is not None and status in profile.accounting_statuses


_ID_ATTRIBUTES = {
    "port": ("NAS-Port", "NAS-Port-Id"),
    "acct_session_id": ("Acct-Session-Id",),
    "h323_conf_id": ("h323-conf-id", "H323-Conf-ID", "Quintum-h323-conf-id", "Acct-Session-Id"),
    "mac_ip": ("mac_ip", "Calling-Station-Id"),
    "interface_index": ("USR-Interface-Index", "NAS-Port"),
    "call_id": ("Sip-Call-ID", "Call-ID", "Acct-Session-Id"),
}


def provider_session_id(ras_type: str | None, attributes: Mapping[str, object]) -> str | None:
    """Return the A1.24 provider online identity when the source defines one.

    Falls back to the standard Acct-Session-Id only when the provider has no
    source-defined identity attribute available.
    """
    profile = provider_profile(ras_type)
    if profile is None:
        raw = attributes.get("Acct-Session-Id")
        return str(raw) if raw not in (None, "") else None
    for name in _ID_ATTRIBUTES.get(profile.unique_id or "", ()):
        raw = attributes.get(name)
        if raw not in (None, ""):
            return str(raw)
    raw = attributes.get("Acct-Session-Id")
    return str(raw) if raw not in (None, "") else None


def provider_ip_assignment_for_attributes(ras_type: str | None, attributes: Mapping[str, object]) -> bool | None:
    profile = provider_profile(ras_type)
    if profile is None:
        return None
    if profile.ip_assignment is not None:
        return profile.ip_assignment
    if profile.name == "mikrotik":
        port_type = str(attributes.get("NAS-Port-Type", "")).strip()
        port_type = {"5": "Virtual", "15": "Ethernet", "19": "Wireless-802.11"}.get(port_type, port_type)
        if port_type == "Wireless-802.11":
            return False
        if port_type in {"Ethernet", "Virtual"}:
            return True
    return None


def provider_disconnect_strategy(ras_type: str | None) -> str | None:
    profile = provider_profile(ras_type)
    return profile.disconnect_strategy if profile else None
