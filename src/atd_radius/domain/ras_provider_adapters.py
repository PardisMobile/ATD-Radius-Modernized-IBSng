"""Concrete, side-effect-free RAS adapters for source-traced A1.24 providers.

Adapters in this module normalize provider-specific packet facts into the
modern domain boundary. They deliberately do not perform SNMP/RSH/launcher
side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .accounting_lifecycle import SessionAction
from .ras_provider import (
    provider_accounting_action,
    provider_ip_assignment_for_attributes,
    provider_session_id,
    provider_multi_login,
    provider_sip_called_number,
    provider_sip_digest_attributes,
    provider_disconnect_strategy,
)
from .ras_external import (
    ProviderOperationRequest,
    build_provider_disconnect_request,
    build_portmaster_disconnect_request,
    build_total_control_disconnect_request,
    build_portslave_disconnect_request,
    build_pppd_disconnect_request,
    build_cisco_vpdn_disconnect_request,
    build_mikrotik_disconnect_request,
)


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


@dataclass(frozen=True, slots=True)
class AsteriskPacketAdapter:
    """Source-traced Asterisk identity/capability boundary."""

    def session_id(self, attributes: Mapping[str, object]) -> str | None:
        return provider_session_id("asterisk", attributes, "voip")

    def multi_login(self, attributes: Mapping[str, object]) -> bool:
        value = attributes.get("asterisk_multi_login", 0)
        try:
            return int(value) != 0
        except (TypeError, ValueError):
            return False


@dataclass(frozen=True, slots=True)
class GnuGkPacketAdapter:
    """Source-traced GnuGk identity/capability boundary."""

    def session_id(self, attributes: Mapping[str, object]) -> str | None:
        return provider_session_id("gnugk", attributes, "voip")

    def multi_login(self, attributes: Mapping[str, object]) -> bool:
        value = attributes.get("gnugk_multiple_login", 0)
        try:
            return int(value) != 0
        except (TypeError, ValueError):
            return False


@dataclass(frozen=True, slots=True)
class MVTSChannelAdapter:
    """Source-traced MVTS H323 conference identity boundary."""

    def session_id(self, attributes: Mapping[str, object]) -> str | None:
        return provider_session_id("mvts", attributes, "voip")


@dataclass(frozen=True, slots=True)
class QuintumTenorAdapter:
    """Source-traced Quintum Tenor identity and single-session boundary."""

    def session_id(self, attributes: Mapping[str, object]) -> str | None:
        return provider_session_id("tenor", attributes, "voip")

    def multi_login(self) -> bool:
        return False

    def single_session_h323(self) -> bool:
        return True


ASTERISK_ADAPTER = AsteriskPacketAdapter()
GNUGK_ADAPTER = GnuGkPacketAdapter()
MVTS_ADAPTER = MVTSChannelAdapter()
QUINTUM_TENOR_ADAPTER = QuintumTenorAdapter()


@dataclass(frozen=True, slots=True)
class ExternalSideEffectAdapter:
    """Transport-neutral boundary for one source-traced provider strategy."""

    provider: str

    def disconnect_strategy(self) -> str | None:
        return provider_disconnect_strategy(self.provider)

    def disconnect_request(
        self, source_parameters: Mapping[str, object]
    ) -> ProviderOperationRequest | None:
        return build_provider_disconnect_request(
            self.provider,
            self.disconnect_strategy(),
            source_parameters=source_parameters,
        )


@dataclass(frozen=True, slots=True)
class CiscoVPDNExternalSideEffectAdapter(ExternalSideEffectAdapter):
    """Cisco VPDN RSH disconnect after source-defined interface discovery."""

    def source_disconnect_request(
        self, source_parameters: Mapping[str, object]
    ) -> ProviderOperationRequest:
        return build_cisco_vpdn_disconnect_request(**source_parameters)


@dataclass(frozen=True, slots=True)
class MikroTikExternalSideEffectAdapter(ExternalSideEffectAdapter):
    """MikroTik RSH-wrapper disconnect with source-derived command selection."""

    def source_disconnect_request(
        self, source_parameters: Mapping[str, object]
    ) -> ProviderOperationRequest:
        return build_mikrotik_disconnect_request(**source_parameters)


@dataclass(frozen=True, slots=True)
class PortSlaveExternalSideEffectAdapter(ExternalSideEffectAdapter):
    """PortSlave's source-derived launcher invocation boundary."""

    def source_disconnect_request(
        self, source_parameters: Mapping[str, object]
    ) -> ProviderOperationRequest:
        return build_portslave_disconnect_request(**source_parameters)


@dataclass(frozen=True, slots=True)
class PPPDExternalSideEffectAdapter(ExternalSideEffectAdapter):
    """PPPD's source-derived launcher invocation boundary."""

    def source_disconnect_request(
        self, source_parameters: Mapping[str, object]
    ) -> ProviderOperationRequest:
        return build_pppd_disconnect_request(**source_parameters)


@dataclass(frozen=True, slots=True)
class PortMasterExternalSideEffectAdapter(ExternalSideEffectAdapter):
    """PortMaster SNMP disconnect request using its exact A1.24 OID mapping."""

    def source_disconnect_request(
        self, source_parameters: Mapping[str, object]
    ) -> ProviderOperationRequest:
        return build_portmaster_disconnect_request(**source_parameters)


@dataclass(frozen=True, slots=True)
class TotalControlExternalSideEffectAdapter(ExternalSideEffectAdapter):
    """Total Control SNMP disconnect request using its source-defined down/up sequence."""

    def source_disconnect_request(
        self, source_parameters: Mapping[str, object]
    ) -> ProviderOperationRequest:
        return build_total_control_disconnect_request(**source_parameters)


CHILLISPOT_EXTERNAL_ADAPTER = ExternalSideEffectAdapter("chilli_spot")
CISCO_VPDN_EXTERNAL_ADAPTER = CiscoVPDNExternalSideEffectAdapter("cisco_vpdn")
MIKROTIK_EXTERNAL_ADAPTER = MikroTikExternalSideEffectAdapter("mikrotik")
PORTMASTER_EXTERNAL_ADAPTER = PortMasterExternalSideEffectAdapter("portmaster")
PORTSLAVE_EXTERNAL_ADAPTER = PortSlaveExternalSideEffectAdapter("portslave")
TOTAL_CONTROL_EXTERNAL_ADAPTER = TotalControlExternalSideEffectAdapter("total_control")
QUINTUM_TENOR_EXTERNAL_ADAPTER = ExternalSideEffectAdapter("tenor")
PPPD_EXTERNAL_ADAPTER = PPPDExternalSideEffectAdapter("pppd")


@dataclass(frozen=True, slots=True)
class CiscoExternalSideEffectAdapter:
    """Cisco keeps two possible external disconnect mechanisms in A1.24.

    The source-derived boundary intentionally does not choose between SNMP and
    RSH until the concrete source branch is available to the runtime adapter.
    """

    provider: str = "cisco"

    def disconnect_strategy(self) -> str | None:
        return provider_disconnect_strategy(self.provider)

    def disconnect_request(
        self, source_parameters: Mapping[str, object]
    ) -> ProviderOperationRequest | None:
        return build_provider_disconnect_request(
            self.provider,
            self.disconnect_strategy(),
            source_parameters=source_parameters,
        )


CISCO_EXTERNAL_ADAPTER = CiscoExternalSideEffectAdapter()
