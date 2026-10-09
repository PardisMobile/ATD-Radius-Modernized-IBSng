"""Session lifecycle adapter for RADIUS Accounting-Request events."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from .accounting_lifecycle import AccountingEvent, AccountingStatus
from .accounting_charge import InternetChargeSettlement
from .radius_runtime import SessionKey, SessionRegistry, SessionState

class AccountingPersistence(Protocol):
    def start(self,event:AccountingEvent,user_id:int,ras_id:int)->int|None: ...
    def update(self,connection_log_id:int,event:AccountingEvent)->None: ...
    def stop(self,connection_log_id:int,event:AccountingEvent,credit_used=None)->None: ...

@dataclass(frozen=True,slots=True)
class AccountingSessionResult:
    state:SessionState
    delta_input_octets:int=0
    delta_output_octets:int=0
    connection_log_id:int|None=None
    credit_used:str|None=None

class AccountingSessionService:
    def __init__(self,registry:SessionRegistry,persistence:AccountingPersistence|None=None,charge:InternetChargeSettlement|None=None):
        self.registry=registry; self.persistence=persistence; self.charge=charge

    def apply(self,event,user_id,ras_id)->AccountingSessionResult:
        if not event.session_id: raise ValueError("Acct-Session-Id is required")
        key=SessionKey(user_id,ras_id,event.session_id); current=self.registry.get(key)
        if event.status is AccountingStatus.START and current is None:
            state=self.registry.start(
                key, dict(event.attributes), event.input_octets, event.output_octets,
                event.observed_at, ras_multi_login_allowed=event.ras_multi_login_allowed
            )
            if self.charge: self.charge.start(state,event.observed_at,ras_id,event.attributes.get("NAS-Port") or event.attributes.get("NAS-Port-Id"))
            log_id=self.persistence.start(event,user_id,ras_id) if self.persistence and "no_connection_log" not in event.attributes else None
            if log_id is not None: state.attributes={**state.attributes,"__connection_log_id":str(log_id)}
            return AccountingSessionResult(state,connection_log_id=log_id)
        if current is not None and current.stopped:
            return AccountingSessionResult(current,connection_log_id=int(current.attributes["__connection_log_id"]) if "__connection_log_id" in current.attributes else None)
        if current is not None and event.status is AccountingStatus.START:
            return AccountingSessionResult(current,connection_log_id=int(current.attributes["__connection_log_id"]) if "__connection_log_id" in current.attributes else None)
        if current is None:
            if event.status is AccountingStatus.INTERIM:
                state=self.registry.start(key,dict(event.attributes),event.input_octets,event.output_octets,event.observed_at)
                if self.charge: self.charge.start(state,event.observed_at,ras_id,event.attributes.get("NAS-Port") or event.attributes.get("NAS-Port-Id"))
                log_id=self.persistence.start(event,user_id,ras_id) if self.persistence and "no_connection_log" not in event.attributes else None
                if log_id is not None: state.attributes={**state.attributes,"__connection_log_id":str(log_id)}
                return AccountingSessionResult(state,connection_log_id=log_id)
            raise LookupError("RADIUS session not found")
        log_id=int(current.attributes["__connection_log_id"]) if "__connection_log_id" in current.attributes else None
        port=event.attributes.get("NAS-Port") or event.attributes.get("NAS-Port-Id")
        if event.status in (AccountingStatus.INTERIM,AccountingStatus.ALIVE):
            di,do=self.registry.update(key,event.input_octets,event.output_octets)
            if self.charge: self.charge.update(current,event.observed_at,ras_id,port)
            if self.persistence and log_id is not None: self.persistence.update(log_id,event)
            return AccountingSessionResult(current,di,do,log_id)
        if event.status is AccountingStatus.STOP:
            di,do=self.registry.update(key,event.input_octets,event.output_octets)
            state=self.registry.stop(key,event.input_octets,event.output_octets)
            used=(Decimal("0") if "no_commit" in event.attributes else self.charge.settle(state,event.observed_at,ras_id,port)) if self.charge else None
            if self.persistence and log_id is not None and "no_connection_log" not in event.attributes:
                self.persistence.stop(log_id,event,used)
            return AccountingSessionResult(state,di,do,log_id,str(used) if used is not None else None)
        raise ValueError(f"unsupported accounting status: {event.status}")
