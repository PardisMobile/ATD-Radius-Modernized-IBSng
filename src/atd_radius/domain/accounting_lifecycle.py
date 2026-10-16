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
    # Internal source-derived policy context; deliberately not a RADIUS attribute.
    ras_multi_login_allowed: bool | None = None
    # Internal service family used to preserve the native connection_log service ID.
    service: str = "internet"

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

def _first_attribute_value(attrs: Mapping[str, object], name: str, default=None):
    """Read the scalar value of an attribute from either decoded packet shape.

    Some RADIUS decoders expose values as scalars while others expose a list
    (matching A1.24 RasMsg's attribute-list interface). Accounting identity and
    policy selectors consume the first value of these single-value attributes.
    """
    value = attrs.get(name, default)
    if isinstance(value, (list, tuple)):
        return value[0] if value else default
    return value


def event_from_attributes(attrs:Mapping[str,object])->AccountingEvent:
    raw = _first_attribute_value(attrs, "Acct-Status-Type", "")
    status_value = str(raw)
    try:
        status = AccountingStatus(status_value)
    except ValueError:
        numeric_status = {"1": AccountingStatus.START, "2": AccountingStatus.STOP, "3": AccountingStatus.INTERIM}.get(status_value)
        if numeric_status is None:
            raise ValueError(f"unsupported Acct-Status-Type: {raw}")
        status = numeric_status
    def integer(name):
        value = _first_attribute_value(attrs, name, 0)
        return int(value)

    def octets(name, gigawords_name):
        value = integer(name)
        gigawords = integer(gigawords_name)
        if gigawords < 0 or value < 0:
            raise ValueError(f"negative accounting counter: {name}")
        return gigawords * (2 ** 32) + value

    return AccountingEvent(
        status=status, username=str(_first_attribute_value(attrs, "User-Name", "")),
        session_id=(
            str(_first_attribute_value(attrs, "Acct-Session-Id"))
            if _first_attribute_value(attrs, "Acct-Session-Id") is not None else None
        ),
        remote_ip=(
            str(_first_attribute_value(attrs, "Framed-IP-Address"))
            if _first_attribute_value(attrs, "Framed-IP-Address") is not None else None
        ),
        input_octets=octets("Acct-Input-Octets", "Acct-Input-Gigawords"), output_octets=octets("Acct-Output-Octets", "Acct-Output-Gigawords"),
        terminate_cause=(
            str(_first_attribute_value(attrs, "Acct-Terminate-Cause"))
            if _first_attribute_value(attrs, "Acct-Terminate-Cause") is not None else None
        ),
        attributes={
            str(name): str(_first_attribute_value(attrs, str(name), ""))
            for name in attrs
        },
    )
