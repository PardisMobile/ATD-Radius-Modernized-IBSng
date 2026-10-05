"""AAA decision primitives matching the IBSng A1.24 plugin pipeline boundary."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Protocol

class AAAAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    CHALLENGE = "challenge"

@dataclass(frozen=True, slots=True)
class AAARequest:
    username: str
    attributes: Mapping[str, str] = field(default_factory=dict)
    protocol: str = "radius"
    service: str = "internet"
    def __post_init__(self):
        if not self.username:
            raise ValueError("username is required")

@dataclass(frozen=True, slots=True)
class AAAResult:
    action: AAAAction
    attributes: Mapping[str, str] = field(default_factory=dict)
    reason: str | None = None

class AAAPolicy(Protocol):
    def evaluate(self, request: AAARequest) -> AAAResult | None: ...

class PluginPipeline:
    """Ordered policy pipeline; first terminal decision wins."""
    def __init__(self, policies: list[AAAPolicy]):
        self._policies = tuple(policies)
    def evaluate(self, request: AAARequest) -> AAAResult:
        merged: dict[str, str] = dict(request.attributes)
        for policy in self._policies:
            result = policy.evaluate(request)
            if result is None:
                continue
            merged.update(result.attributes)
            if result.action is not AAAAction.ACCEPT:
                return AAAResult(result.action, merged, result.reason)
        return AAAResult(AAAAction.ACCEPT, merged)
