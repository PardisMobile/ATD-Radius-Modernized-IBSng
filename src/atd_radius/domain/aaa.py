"""Ordered A1.24-style plugin hook execution."""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import StrEnum
from typing import Mapping,Protocol

class AAAAction(StrEnum):
    ACCEPT="accept"; REJECT="reject"; CHALLENGE="challenge"

@dataclass(frozen=True,slots=True)
class AAARequest:
    username:str
    attributes:Mapping[str,str]=field(default_factory=dict)
    protocol:str="radius"
    service:str="internet"
    def __post_init__(self):
        if not self.username: raise ValueError("username is required")

@dataclass(frozen=True,slots=True)
class AAAResult:
    action:AAAAction
    attributes:Mapping[str,str]=field(default_factory=dict)
    reason:str|None=None

class AAAPolicy(Protocol):
    def evaluate(self,request:AAARequest)->AAAResult|None: ...

@dataclass(frozen=True,slots=True)
class PluginSpec:
    priority:int
    name:str
    policy:AAAPolicy

class PluginPipeline:
    """A1.24 priorities 0..9; lower priority number executes first."""
    def __init__(self,policies:list[AAAPolicy]|list[PluginSpec]):
        specs=[]
        for index,item in enumerate(policies):
            if isinstance(item,PluginSpec):
                specs.append((index, item))
            else:
                specs.append((index, PluginSpec(5,str(index),item)))
        # A1.24 preserves registration order inside each numeric priority bucket.
        self._plugins=tuple(item for _,item in sorted(specs,key=lambda pair:(max(0,min(9,pair[1].priority)),pair[0])))
    @property
    def plugins(self): return self._plugins
    def evaluate(self,request:AAARequest)->AAAResult:
        merged=dict(request.attributes)
        for spec in self._plugins:
            result=spec.policy.evaluate(AAARequest(request.username,merged,request.protocol,request.service))
            if result is None: continue
            merged.update(result.attributes)
            if result.action is not AAAAction.ACCEPT:
                return AAAResult(result.action,merged,result.reason)
        return AAAResult(AAAAction.ACCEPT,merged)
