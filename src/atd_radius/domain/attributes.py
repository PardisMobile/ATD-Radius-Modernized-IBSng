"""IBSng-style attribute resolution.

Precedence is intentionally explicit: RAS -> Group(s) -> Service(s) -> User.
Later scopes override earlier scopes. A future version may add plugin-specific
merge strategies; the default remains deterministic last-writer-wins.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .models import AttributeSet


def resolve_attributes(
    ras: Mapping[str, Any] | None = None,
    groups: Iterable[Mapping[str, Any]] = (),
    services: Iterable[Mapping[str, Any]] = (),
    user: Mapping[str, Any] | None = None,
) -> AttributeSet:
    result: dict[str, Any] = {}
    for scope in (ras or {}, *groups, *services, user or {}):
        result.update(scope)
    return AttributeSet(result)
