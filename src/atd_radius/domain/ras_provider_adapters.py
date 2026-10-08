"""Concrete, side-effect-free RAS adapters for source-traced A1.24 providers.

Adapters in this module normalize provider-specific packet facts into the
modern domain boundary. They deliberately do not perform SNMP/RSH/launcher
side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .accounting_lifecycle import SessionAction
from .ras_provider import (\n    provider_accounting_action,\n    provider_ip_assignment_for_attributes,\n    provider_session_id,\n)


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
