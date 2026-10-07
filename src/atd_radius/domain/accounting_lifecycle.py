"""Accounting lifecycle primitives mapped from A1.24 RasMsg actions."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping

class AccountingStatus(StrEnum):
    START="Start"; STOP="Stop"; INTERIM="Interim-Update"; ALIVE="Alive"

class SessionAction(StrEnum):
    INTERNET_AUTHENTICATE="INTERNET_AUTHENTICATE"; INTERNET_UPDATE="INTERNET_UPDATE"; INTERNET_STOP="INTERNET_STOP"
    PERSISTENT_LAN_AUTHENTICATE="PERSISTENT_LAN_AUTHENTICATE"; PERSISTENT_LAN_STOP="PERSISTENT_LAN_STOP"
    VOIP_AUTHENTICATE="VOIP_AUTHENTICATE"; VOIP_AUTHORIZE="VOIP_AUTHORIZE"; VOIP_UPDATE="VOIP_UPDATE"; VOIP_STOP="VOIP_STOP"

@dataclass(frozen=True, slots=True)
class AccountingEvent:
    status: AccountingStatus
    username: str
    session_id: str | None = None
    remote_ip: str | None = None
    input_octets: int = 0
    output_octets: int = 0
    terminate_cause: str | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass(slots=True)
class SessionUsage:
    input_octets:int=0; output_octets:int=0; last_input_octets:int=0; last_output_octets:int=0; started:bool=False
    def start(self,event):
        self.started=True; self.last_input_octets=self.input_octets=event.input_octets; self.last_output_octets=self.output_octets=event.output_octets
    def interim(self,event):
        if not self.started: self.start(event); return (0,0)
        delta=(max(0,event.input_octets-self.last_input_octets),max(0,event.output_octets-self.last_output_octets))
        self.input_octets,self.output_octets=event.input_octets,event.output_octets
        self.last_input_octets,self.last_output_octets=event.input_octets,event.output_octets
        return delta
    def stop(self,event): return self.interim(event)

def event_from_attributes(attrs:Mapping[str,object])->AccountingEvent:
    raw=str(attrs.get("Acct-Status-Type",""))
    try: status=AccountingStatus(raw)
    except ValueError as exc: raise ValueError(f"unsupported Acct-Status-Type: {raw}") from exc
    def integer(name):
        value=attrs.get(name,0); return int(value[0] if isinstance(value,(list,tuple)) else value)

    def octets(name, gigawords_name):
        value = integer(name)
        gigawords = integer(gigawords_name)
        if gigawords < 0 or value < 0:
            raise ValueError(f"negative accounting counter: {name}")
        return gigawords * (2 ** 32) + value

    return AccountingEvent(
        status=status, username=str(attrs.get("User-Name","")),
        session_id=str(attrs["Acct-Session-Id"]) if attrs.get("Acct-Session-Id") is not None else None,
        remote_ip=str(attrs["Framed-IP-Address"]) if attrs.get("Framed-IP-Address") is not None else None,
        input_octets=octets("Acct-Input-Octets", "Acct-Input-Gigawords"), output_octets=octets("Acct-Output-Octets", "Acct-Output-Gigawords"),
        terminate_cause=str(attrs["Acct-Terminate-Cause"]) if attrs.get("Acct-Terminate-Cause") is not None else None,
        attributes={str(name):str(value) for name,value in attrs.items()},
    )
