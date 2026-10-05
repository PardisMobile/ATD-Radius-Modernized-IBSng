"""Ordered A1.24-style plugin hook execution."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Protocol

class AAAAction(StrEnum):
    ACCEPT="accept"; REJECT="reject"; CHALLENGE="challenge"

@dataclass(frozen=True, slots=True)
class AAARequest:
    username: str
    attributes: Mapping[str,str]=field(default_factory=dict)
    protocol: str="radius"
    service: str="internet"
    def __post_init__(self):
        if not self.username: raise ValueError("username is required")

@dataclass(frozen=True, slots=True)
class AAAResult:
    action: AAAAction
    attributes: Mapping[str,str]=field(default_factory=dict)
    reason: str|None=None

class AAAPolicy(Protocol):
    def evaluate(self, request: AAARequest) -> AAAResult|None: ...

class PluginPipeline:
    """Run every plugin in deterministic order; reject/challenge are terminal."""
    def __init__(self, policies:list[AAAPolicy]): self._policies=tuple(policies)
    def evaluate(self, request:AAARequest)->AAAResult:
        merged=dict(request.attributes)
        for policy in self._policies:
            result=policy.evaluate(AAARequest(request.username,merged,request.protocol,request.service))
            if result is None: continue
            merged.update(result.attributes)
            if result.action is not AAAAction.ACCEPT:
                return AAAResult(result.action,merged,result.reason)
        return AAAResult(AAAAction.ACCEPT,merged)
