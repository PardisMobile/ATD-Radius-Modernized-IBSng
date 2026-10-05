"""RADIUS request/response boundary for ATD's modern AAA engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping
class RadiusCode(StrEnum):
    ACCESS_REQUEST="Access-Request"; ACCESS_ACCEPT="Access-Accept"; ACCESS_REJECT="Access-Reject"; ACCESS_CHALLENGE="Access-Challenge"; ACCOUNTING_REQUEST="Accounting-Request"; ACCOUNTING_RESPONSE="Accounting-Response"
@dataclass(frozen=True, slots=True)
class RadiusPacket:
    code: RadiusCode
    identifier: int
    attributes: Mapping[str,str]=field(default_factory=dict)
    authenticator: bytes=b""
    def __post_init__(self):
        if not 0 <= self.identifier <= 255: raise ValueError("RADIUS identifier must be 0..255")
def response_for_access(request: RadiusPacket, action: str, attributes: Mapping[str,str]|None=None)->RadiusPacket:
    mapping={"accept":RadiusCode.ACCESS_ACCEPT,"reject":RadiusCode.ACCESS_REJECT,"challenge":RadiusCode.ACCESS_CHALLENGE}
    if request.code is not RadiusCode.ACCESS_REQUEST: raise ValueError("access response requires Access-Request")
    if action not in mapping: raise ValueError("invalid AAA action")
    return RadiusPacket(mapping[action],request.identifier,attributes or {},request.authenticator)
