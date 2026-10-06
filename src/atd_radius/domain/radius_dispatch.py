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
    def enrich(self, packet: RadiusPacket) -> Mapping[str, str]: ...

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
        return response_for_access(packet,result.action.value,result.attributes)
    def accounting(self,packet:RadiusPacket)->DispatchResult:
        if packet.code is not RadiusCode.ACCOUNTING_REQUEST: raise ValueError("expected Accounting-Request")
        return DispatchResult(RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE,packet.identifier,{},packet.authenticator),event_from_attributes(packet.attributes))
    def control(self,code:str,attributes:Mapping[str,str])->str:
        if self.session_control is None: return "nack"
        if code==DisconnectCode.DISCONNECT_REQUEST: return "ack" if self.session_control.disconnect(attributes) else "nack"
        if code==DisconnectCode.COA_REQUEST: return "ack" if self.session_control.change_of_authorization(attributes) else "nack"
        raise ValueError("unsupported control packet")
