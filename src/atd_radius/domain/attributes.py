"""Typed IBSng-compatible attribute and policy resolution.

Attributes are policy objects, not merely key/value pairs. Scope, precedence,
operator, multiplicity and provenance remain explicit so protocol adapters do
not implement policy themselves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any, Iterable

from .models import AttributeSet


class AttributeScope(StrEnum):
    SYSTEM = "system"
    RAS = "ras"
    SERVICE = "service"
    GROUP = "group"
    USER = "user"


class AttributeOperator(StrEnum):
    SET = "set"
    ADD = "add"
    REMOVE = "remove"
    REPLACE = "replace"


class AttributePriority(IntEnum):
    SYSTEM = 10
    RAS = 20
    SERVICE = 30
    GROUP = 40
    USER = 50


@dataclass(frozen=True, slots=True)
class AttributeDefinition:
    name: str
    value_type: str = "string"
    multi: bool = False
    operators: tuple[AttributeOperator, ...] = (AttributeOperator.SET,)
    description: str = ""
    radius_name: str | None = None
    enforcement: str | None = None


@dataclass(frozen=True, slots=True)
class AttributeValue:
    name: str
    value: Any
    scope: AttributeScope
    priority: int | None = None
    operator: AttributeOperator = AttributeOperator.SET
    source_id: str | None = None
    enabled: bool = True

    @property
    def effective_priority(self) -> int:
        return self.priority if self.priority is not None else AttributePriority[self.scope.name]


@dataclass(slots=True)
class EffectiveAttributes(AttributeSet):
    """Resolved values plus a provenance trail for operator/debugging UI."""

    sources: dict[str, list[AttributeValue]] = field(default_factory=dict)

    def explain(self, name: str) -> list[AttributeValue]:
        return list(self.sources.get(name, ()))


class AttributeValidationError(ValueError):
    pass


def _coerce(definition: AttributeDefinition, value: Any) -> Any:
    if definition.value_type == "string":
        return value if isinstance(value, str) else str(value)
    if definition.value_type == "integer":
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise AttributeValidationError(f"{definition.name}: expected integer") from exc
    if definition.value_type == "boolean":
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "1", "yes", "on"}:
            return True
        if str(value).lower() in {"false", "0", "no", "off"}:
            return False
        raise AttributeValidationError(f"{definition.name}: expected boolean")
    return value


def resolve_typed_attributes(
    definitions: dict[str, AttributeDefinition],
    layers: Iterable[Iterable[AttributeValue]],
) -> EffectiveAttributes:
    """Resolve policy layers deterministically while retaining provenance."""
    candidates = [a for layer in layers for a in layer if a.enabled]
    candidates.sort(key=lambda a: (a.effective_priority, a.source_id or ""))
    result = EffectiveAttributes(values={})

    for attr in candidates:
        definition = definitions.get(attr.name, AttributeDefinition(attr.name))
        value = _coerce(definition, attr.value)
        if attr.operator not in definition.operators:
            raise AttributeValidationError(
                f"{attr.name}: operator {attr.operator} is not permitted"
            )
        current = result.values.get(attr.name)
        if attr.operator in (AttributeOperator.SET, AttributeOperator.REPLACE):
            result.values[attr.name] = [value] if definition.multi else value
        elif attr.operator is AttributeOperator.ADD:
            if not definition.multi:
                raise AttributeValidationError(f"{attr.name}: ADD requires multi-value attribute")
            values = list(current or [])
            if value not in values:
                values.append(value)
            result.values[attr.name] = values
        elif attr.operator is AttributeOperator.REMOVE:
            if not definition.multi:
                raise AttributeValidationError(f"{attr.name}: REMOVE requires multi-value attribute")
            result.values[attr.name] = [v for v in list(current or []) if v != value]
        result.sources.setdefault(attr.name, []).append(attr)

    return result


def resolve_attributes(
    ras: dict[str, Any] | None = None,
    groups: Iterable[dict[str, Any]] = (),
    services: Iterable[dict[str, Any]] = (),
    user: dict[str, Any] | None = None,
) -> AttributeSet:
    """Backward-compatible simple resolver for existing callers."""
    result: dict[str, Any] = {}
    for scope in (ras or {}, *groups, *services, user or {}):
        result.update(scope)
    return AttributeSet(result)
