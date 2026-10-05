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

class SessionControl(Protocol):
    def disconnect(self,attributes:Mapping[str,str])->bool: ...
    def change_of_authorization(self,attributes:Mapping[str,str])->bool: ...

class RadiusDispatcher:
    def __init__(self,pipeline:PluginPipeline,session_control:SessionControl|None=None):
        self.pipeline=pipeline; self.session_control=session_control
    def access(self,packet:RadiusPacket)->RadiusPacket:
        if packet.code is not RadiusCode.ACCESS_REQUEST: raise ValueError("expected Access-Request")
        result=self.pipeline.evaluate(AAARequest(packet.attributes.get("User-Name",""),packet.attributes))
        return response_for_access(packet,result.action.value,result.attributes)
    def accounting(self,packet:RadiusPacket)->DispatchResult:
        if packet.code is not RadiusCode.ACCOUNTING_REQUEST: raise ValueError("expected Accounting-Request")
        return DispatchResult(RadiusPacket(RadiusCode.ACCOUNTING_RESPONSE,packet.identifier,{},packet.authenticator),event_from_attributes(packet.attributes))
    def control(self,code:str,attributes:Mapping[str,str])->str:
        if self.session_control is None: return "nack"
        if code==DisconnectCode.DISCONNECT_REQUEST: return "ack" if self.session_control.disconnect(attributes) else "nack"
        if code==DisconnectCode.COA_REQUEST: return "ack" if self.session_control.change_of_authorization(attributes) else "nack"
        raise ValueError("unsupported control packet")
