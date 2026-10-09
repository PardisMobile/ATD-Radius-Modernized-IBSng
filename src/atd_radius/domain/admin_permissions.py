"""Source-shaped IBSng A1.24 administrator permission evaluation.

This is an authorization primitive, not an authentication/session implementation.
Permission names and value semantics must be registered from source-backed definitions;
unknown permissions are denied rather than inferred from their names.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Sequence


class PermissionKind(str, Enum):
    NO_VALUE = "no_value"
    SINGLE_VALUE = "single_value"
    MULTI_VALUE = "multi_value"
    CONTEXTUAL = "contextual"


@dataclass(frozen=True)
class PermissionSpec:
    name: str
    kind: PermissionKind
    dependencies: tuple[str, ...] = ()
    evaluator: Callable[[str | None, Mapping[str, object]], bool] | None = None


@dataclass(frozen=True)
class AdminPermissionSet:
    """An administrator's persisted permission values, keyed by native perm_name."""

    values: Mapping[str, str | None]

    def has_perm(self, name: str) -> bool:
        """Match A1.24 hasPerm: presence only, not authorization/value evaluation."""
        return name in self.values

    def is_god(self) -> bool:
        # A1.24 defines GOD by permission presence.
        return self.has_perm("GOD")


class AdminPermissionEvaluator:
    """Evaluate only explicitly registered, source-backed permission definitions."""

    def __init__(self, specs: Sequence[PermissionSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}
        if len(self._specs) != len(specs):
            raise ValueError("duplicate administrator permission specification")

    def check_perm(
        self,
        permissions: AdminPermissionSet,
        name: str,
        *,
        requested_value: str | None = None,
        context: Mapping[str, object] | None = None,
        _visited: frozenset[str] = frozenset(),
    ) -> bool:
        """Check value and dependency rules; unknown definitions fail closed."""
        if name in _visited:
            return False
        spec = self._specs.get(name)
        if spec is None or not permissions.has_perm(name):
            return False

        value = permissions.values[name]
        ctx = context or {}
        visited = _visited | {name}
        for dependency in spec.dependencies:
            if not self.check_perm(permissions, dependency, context=ctx, _visited=visited):
                return False

        if spec.kind is PermissionKind.NO_VALUE:
            return True
        if spec.kind is PermissionKind.SINGLE_VALUE:
            return value is not None and requested_value is not None and value == requested_value
        if spec.kind is PermissionKind.MULTI_VALUE:
            allowed = [] if value is None or value == "" else value.split(",")
            return requested_value is not None and requested_value in allowed
        if spec.kind is PermissionKind.CONTEXTUAL:
            return spec.evaluator is not None and bool(spec.evaluator(value, ctx))
        return False

    def can_do(
        self,
        permissions: AdminPermissionSet,
        name: str,
        *,
        requested_value: str | None = None,
        context: Mapping[str, object] | None = None,
    ) -> bool:
        """A1.24-style GOD bypass applies to canDo, not to hasPerm/checkPerm."""
        if permissions.is_god():
            return True
        return self.check_perm(
            permissions, name, requested_value=requested_value, context=context
        )


def parse_permission_value(kind: PermissionKind, value: str | None) -> str | list[str] | None:
    """Parse native text values without converting empty values into grants."""
    if kind is PermissionKind.MULTI_VALUE:
        return [] if not value else value.split(",")
    return value
