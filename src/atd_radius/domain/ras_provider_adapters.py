"""Concrete, side-effect-free RAS adapters for source-traced A1.24 providers.

Adapters in this module normalize provider-specific packet facts into the
modern domain boundary. They deliberately do not perform SNMP/RSH/launcher
side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .accounting_lifecycle import SessionAction
from .ras_provider import (\n    provider_accounting_action,\n    provider_ip_assignment_for_attributes,\n    provider_session_id,\n    provider_multi_login,\n    provider_sip_called_number,\n    provider_sip_digest_attributes,\n)


@dataclass(frozen=True, slots=True)
class MikroTikPacketAdapter:
    """A1.24-derived MikroTik Internet packet normalization."""

    def session_id(self, attributes: Mapping[str, object]) -> str | None:
        return provider_session_id("mikrotik", attributes, "internet")

    def ip_assignment(self, attributes: Mapping[str, object]) -> bool | None:
        return provider_ip_assignment_for_attributes("mikrotik", attributes)

    def accounting_action(self, status: str) -> SessionAction | None:
        return provider_accounting_action("mikrotik", status, "internet")


MIKROTIK_ADAPTER = MikroTikPacketAdapter()


@dataclass(frozen=True, slots=True)
class PersistentLanPacketAdapter:
    """Source-traced PersistentLanRas normalization."""

    def session_id(self, attributes: Mapping[str, object]) -> str | None:
        return provider_session_id("plan", attributes, "internet")

    def ip_assignment(self) -> bool:
        return False

    def persistent_lan(self) -> bool:
        return True

    def accounting_action(self, status: str) -> SessionAction | None:
        return provider_accounting_action("plan", status, "persistent_lan")


@dataclass(frozen=True, slots=True)
class SERPacketAdapter:
    """Source-traced SIP/SER normalization without external SIP side effects."""

    def session_id(self, attributes: Mapping[str, object]) -> str | None:
        return provider_session_id("ser", attributes, "voip")

    def called_number(self, attributes: Mapping[str, object]) -> str | None:
        return provider_sip_called_number(attributes)

    def digest_attributes(self, attributes: Mapping[str, object]) -> dict[str, object]:
        return provider_sip_digest_attributes(attributes)

    def multi_login(self) -> bool | None:
        return provider_multi_login("ser", "voip")

    def accounting_action(self, status: str) -> SessionAction | None:
        # A1.24 ties SER Start to SIP INVITE/call-id creation and Stop to
        # removal of the call-id. No generic Alive mapping is inferred.
        return {
            "Start": SessionAction.VOIP_AUTHENTICATE,
            "Stop": SessionAction.VOIP_STOP,
        }.get(status)


PERSISTENT_LAN_ADAPTER = PersistentLanPacketAdapter()
SER_ADAPTER = SERPacketAdapter()
