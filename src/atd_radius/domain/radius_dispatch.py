"""Protocol dispatch boundary for the A1.24 message families."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping,Protocol
from .aaa import AAARequest,PluginPipeline
from .accounting_lifecycle import event_from_attributes,AccountingEvent
from .radius import RadiusCode,RadiusPacket,response_for_access

class DisconnectCode(StrEnum):
    DISCONNECT_REQUEST="Disconnect-Request"; DISCONNECT_ACK="Disconnect-ACK"; DISCONNECT_NACK="Disconnect-NAK"
    COA_REQUEST="CoA-Request"; COA_ACK="CoA-ACK"; COA_NACK="CoA-NAK"

@dataclass(frozen=True,slots=True)
class DispatchResult:
    response:RadiusPacket
    accounting:AccountingEvent|None=None

class AccessContext(Protocol):
    def enrich(self, packet: RadiusPacket, source_ip: str | None = None) -> Mapping[str, str]: ...

class SessionControl(Protocol):
    def disconnect(self,attributes:Mapping[str,str])->bool: ...
    def change_of_authorization(self,attributes:Mapping[str,str])->bool: ...

class RadiusDispatcher:
    def __init__(self,pipeline:PluginPipeline,session_control:SessionControl|None=None,access_context:AccessContext|None=None):
        self.pipeline=pipeline; self.session_control=session_control; self.access_context=access_context
    def access(self,packet:RadiusPacket, source_ip: str | None = None)->RadiusPacket:
        if packet.code is not RadiusCode.ACCESS_REQUEST: raise ValueError("expected Access-Request")
        attributes=dict(packet.attributes)
        if self.access_context is not None:
            attributes.update(self.access_context.enrich(packet, source_ip))
        result=self.pipeline.evaluate(AAARequest(attributes.get("User-Name",""),attributes))
        if result.action.value == "accept" and self.access_context is not None:
            commit_effects = getattr(self.access_context, "commit_login_effects", None)
            if callable(commit_effects):
                commit_effects(attributes)
        response = response_for_access(packet,result.action.value,result.attributes)
        if response.code is RadiusCode.ACCESS_ACCEPT and self.access_context is not None:
            assign = getattr(self.access_context, "assigned_ip_for_accept", None)
            if callable(assign):
                address = assign(packet, attributes)
                if address:
                    reply_attributes = dict(response.attributes)
                    reply_attributes["Framed-IP-Address"] = str(address)
                    response = RadiusPacket(response.code, response.identifier, reply_attributes, response.authenticator)
        return response
    def accounting(self,packet:RadiusPacket)->DispatchResult:
        if packet.code is not RadiusCode.ACCOUNTING_REQUEST: raise ValueError("expected Accounting-Request")
        return DispatchResult(RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE,packet.identifier,{},packet.authenticator),event_from_attributes(packet.attributes))
    def control(self, packet: RadiusPacket, *, ras_id: int | None = None) -> RadiusPacket:
        if packet.code is RadiusCode.DISCONNECT_REQUEST:
            if self.session_control is None:
                result = False
            elif ras_id is None:
                result = self.session_control.disconnect(packet.attributes)
            else:
                result = self.session_control.disconnect(packet.attributes, ras_id=ras_id)
            code = RadiusCode.DISCONNECT_ACK if (result.ok if hasattr(result, "ok") else result) else RadiusCode.DISCONNECT_NAK
        elif packet.code is RadiusCode.COA_REQUEST:
            if self.session_control is None:
                result = False
            elif ras_id is None:
                result = self.session_control.change_of_authorization(packet.attributes)
            else:
                result = self.session_control.change_of_authorization(packet.attributes, ras_id=ras_id)
            code = RadiusCode.COA_ACK if (result.ok if hasattr(result, "ok") else result) else RadiusCode.COA_NAK
        else:
            raise ValueError("unsupported control packet")
        attrs = {}
        error_cause = getattr(result, "error_cause", None)
        if error_cause is not None and code in {RadiusCode.DISCONNECT_NAK, RadiusCode.COA_NAK}:
            attrs["Error-Cause"] = error_cause
        return RadiusPacket(code, packet.identifier, attrs, packet.authenticator)
