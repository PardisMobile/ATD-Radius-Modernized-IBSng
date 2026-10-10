"""Runtime primitives for A1.24 RADIUS duplicate handling and session state."""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timezone
from time import monotonic
from threading import RLock
from functools import wraps
from typing import Generic, Mapping, TypeVar

T=TypeVar("T")

def _registry_locked(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped

@dataclass(frozen=True,slots=True)
class RequestKey:
    source_ip:str
    source_port:int
    identifier:int
    code:int

@dataclass(slots=True)
class CachedRequest(Generic[T]):
    key:RequestKey
    response:T|None=None
    finished:bool=False
    created_at:float=field(default_factory=monotonic)

class DuplicateRequestCache(Generic[T]):
    def __init__(self): self._items:dict[RequestKey,CachedRequest[T]]={}
    @_registry_locked
    def get(self,key:RequestKey)->CachedRequest[T]|None: return self._items.get(key)
    def add(self,key:RequestKey)->CachedRequest[T]:
        item=CachedRequest(key); self._items[key]=item; return item
    def finish(self,key:RequestKey,response:T)->None:
        item=self._items[key]; item.response=response; item.finished=True
    def remove(self,key:RequestKey)->None: self._items.pop(key,None)
    def purge_expired(self,max_age_seconds:float,now:float|None=None)->int:
        if max_age_seconds<0: raise ValueError("max_age_seconds must be non-negative")
        current=monotonic() if now is None else now
        expired=[key for key,item in self._items.items() if current-item.created_at>=max_age_seconds]
        for key in expired: del self._items[key]
        return len(expired)
    def __len__(self): return len(self._items)

@dataclass(frozen=True,slots=True)
class SessionKey:
    user_id:int
    ras_id:int
    unique_id:str

@dataclass(slots=True)
class SessionState:
    key:SessionKey
    attributes:Mapping[str,str]=field(default_factory=dict)
    started:bool=False
    stopped:bool=False
    input_octets:int=0
    output_octets:int=0
    started_at:datetime|None=None
    charge_id:int|None=None
    charge_rule_id:int|None=None
    charge_rule_started_at:datetime|None=None
    charge_rule_input_octets:int=0
    charge_rule_output_octets:int=0
    charge_accrued: Decimal = field(default_factory=lambda: Decimal("0"))
    ras_multi_login_allowed: bool | None = None

class SessionRegistry:
    def __init__(self):
        self._sessions:dict[SessionKey,SessionState]={}
        self._lock = RLock()

    def synchronized(self):
        """Hold the registry lock across a compound session lifecycle operation."""
        return self._lock
    @_registry_locked
    def start(self,key,attributes=None,input_octets=0,output_octets=0,started_at=None,ras_multi_login_allowed=None)->SessionState:
        state=SessionState(
            key, attributes or {}, True, False, input_octets, output_octets,
            started_at or datetime.now(timezone.utc),
            ras_multi_login_allowed=ras_multi_login_allowed,
        )
        self._sessions[key]=state; return state
    def get(self,key): return self._sessions.get(key)
    @_registry_locked
    def update(self,key,input_octets,output_octets):
        state=self._sessions[key]
        di=max(0,input_octets-state.input_octets); do=max(0,output_octets-state.output_octets)
        state.input_octets=input_octets; state.output_octets=output_octets
        return di,do
    @_registry_locked
    def stop(self,key,input_octets=0,output_octets=0):
        state=self._sessions[key]; state.input_octets=input_octets; state.output_octets=output_octets; state.stopped=True; return state
    @_registry_locked
    def find_by_unique_id(self,unique_id): 
        for state in self._sessions.values():
            if state.key.unique_id==unique_id: return state
        return None
    @_registry_locked
    def matching(self,attributes):
        names={"NAS-IP-Address","NAS-Identifier","User-Name","NAS-Port","Framed-IP-Address","Calling-Station-Id","Called-Station-Id","Acct-Session-Id","Acct-Multi-Session-Id","NAS-Port-Id","Chargeable-User-Identity"}
        ids={k:v for k,v in attributes.items() if k in names}
        if not ids:return ()
        return tuple(s for s in self._sessions.values() if s.started and not s.stopped and all(s.attributes.get(k)==v for k,v in ids.items()))
    @_registry_locked
    def disconnect_matching(self,attributes):
        matches=self.matching(attributes)
        for state in matches: state.stopped=True
        return matches
    @_registry_locked
    def apply_authorization(self,attributes):
        matches=self.matching(attributes); changes={k:v for k,v in attributes.items() if k in {"Filter-Id","NAS-Filter-Rule"}}
        if not changes:return ()
        for state in matches:
            updated=dict(state.attributes); updated.update(changes); state.attributes=updated
        return matches
    @_registry_locked
    def active_for_user(self,user_id):
        return tuple(s for s in self._sessions.values() if s.key.user_id==user_id and s.started and not s.stopped)
