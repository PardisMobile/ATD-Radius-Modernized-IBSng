"""Runtime primitives for A1.24 RADIUS duplicate handling and session state."""
from __future__ import annotations
from dataclasses import dataclass, field
from time import monotonic
from typing import Generic, Mapping, TypeVar

T=TypeVar("T")

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
    """A1.24 request-list semantics: one in-flight request per RADIUS key."""
    def __init__(self): self._items:dict[RequestKey,CachedRequest[T]]={}
    def get(self,key:RequestKey)->CachedRequest[T]|None: return self._items.get(key)
    def add(self,key:RequestKey)->CachedRequest[T]:
        item=CachedRequest(key); self._items[key]=item; return item
    def finish(self,key:RequestKey,response:T)->None:
        item=self._items[key]; item.response=response; item.finished=True
    def remove(self,key:RequestKey)->None: self._items.pop(key,None)
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

class SessionRegistry:
    def __init__(self): self._sessions:dict[SessionKey,SessionState]={}
    def start(self,key:SessionKey,attributes:Mapping[str,str]|None=None)->SessionState:
        state=SessionState(key,attributes or {},True,False)
        self._sessions[key]=state; return state
    def get(self,key:SessionKey)->SessionState|None: return self._sessions.get(key)
    def update(self,key:SessionKey,input_octets:int,output_octets:int)->tuple[int,int]:
        state=self._sessions[key]
        delta=(input_octets-state.input_octets,output_octets-state.output_octets)
        state.input_octets=input_octets; state.output_octets=output_octets
        return delta
    def stop(self,key:SessionKey,input_octets:int=0,output_octets:int=0)->SessionState:
        state=self._sessions[key]
        state.input_octets=input_octets; state.output_octets=output_octets; state.stopped=True
        return state
    def active_for_user(self,user_id:int)->tuple[SessionState,...]:
        return tuple(s for s in self._sessions.values() if s.key.user_id==user_id and s.started and not s.stopped)
