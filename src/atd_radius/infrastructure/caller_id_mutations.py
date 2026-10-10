"""Source-compatible persistence for the special IBSng A1.24 caller_id plugin."""
from __future__ import annotations

import re
from itertools import product

from atd_radius.infrastructure.user_attribute_mutations import (
    AUDIT_LOG_NOVALUE,
    UserAttributeMutationError,
    UserAttributeMutationRepository,
    UserAttributeTarget,
    is_user_audit_log_enabled,
)

_RANGE = re.compile(r"({[nl]?[0-9]+-[0-9]+})")
_RANGE_BODY = re.compile(r"^\{([nl]?)([0-9]+)-([0-9]+)\}$")
_MAX_EXPANSION = 1_000_000


def _expand_component(component: str) -> list[str]:
    """Expand the A1.24 MultiStr/RangeString expression syntax."""
    parts = _RANGE.split(component)
    options: list[list[str]] = []
    for part in parts:
        if not part:
            continue
        match = _RANGE_BODY.fullmatch(part)
        if match is None:
            options.append([part])
            continue
        prefix, start_text, end_text = match.groups()
        start, end = int(start_text), int(end_text)
        if end <= start:
            raise UserAttributeMutationError(f"invalid caller ID range: {part}")
        count = end - start + 1
        if count > _MAX_EXPANSION:
            raise UserAttributeMutationError("caller ID range exceeds safe expansion limit")
        width = max(len(start_text), len(end_text))
        values = [str(n) if prefix == "n" else str(n).zfill(width) for n in range(start, end + 1)]
        options.append(values)
    total = 1
    for option in options:
        total *= len(option)
        if total > _MAX_EXPANSION:
            raise UserAttributeMutationError("caller ID expression exceeds safe expansion limit")
    return ["".join(items) for items in product(*options)] if options else [""]


def expand_caller_ids(expression: str) -> list[str]:
    """Match A1.24 MultiStr comma lists, including embedded numeric ranges."""
    if not expression:
        raise UserAttributeMutationError("caller IDs must not be empty")
    result: list[str] = []
    for component in expression.split(","):
        result.extend(_expand_component(component))
        if len(result) > _MAX_EXPANSION:
            raise UserAttributeMutationError("caller ID expression exceeds safe expansion limit")
    if any(not caller_id for caller_id in result):
        raise UserAttributeMutationError("caller IDs must not contain empty values")
    if len(set(result)) != len(result):
        raise UserAttributeMutationError("caller IDs must be unique")
    return result


class CallerIDMutationRepository:
    """Implement caller_id_users semantics while preserving native audit logging."""

    def __init__(self, conn) -> None:
        self.conn = conn
        self.users = UserAttributeMutationRepository(conn)

    def lock_target(self, username: str) -> UserAttributeTarget | None:
        return self.users.lock_target(username)

    def change(self, target: UserAttributeTarget, *, admin_id: int, expression: str) -> list[str]:
        caller_ids = expand_caller_ids(expression)
        # The A1.24 implementation documents its uniqueness check as not thread-safe.
        # Serialize mutations against the native global primary-key domain.
        self.conn.execute("LOCK TABLE caller_id_users IN SHARE ROW EXCLUSIVE MODE")
        current_rows = self.conn.execute(
            "SELECT caller_id FROM caller_id_users WHERE user_id = %s ORDER BY caller_id",
            (target.user_id,),
        ).fetchall()
        current = [str(row[0]) for row in current_rows]
        current_set = set(current)
        candidates = [value for value in caller_ids if value not in current_set]
        if candidates:
            rows = self.conn.execute(
                "SELECT caller_id FROM caller_id_users WHERE caller_id = ANY(%s)",
                (candidates,),
            ).fetchall()
            existing = [str(row[0]) for row in rows]
            if existing:
                raise UserAttributeMutationError(
                    "caller IDs already assigned: " + ", ".join(sorted(existing))
                )
        self.conn.execute("DELETE FROM caller_id_users WHERE user_id = %s", (target.user_id,))
        for caller_id in caller_ids:
            self.conn.execute(
                "INSERT INTO caller_id_users (user_id, caller_id) VALUES (%s, %s)",
                (target.user_id, caller_id),
            )
        old_value = ",".join(current) if current else AUDIT_LOG_NOVALUE
        new_value = ",".join(caller_ids)
        if old_value != new_value and is_user_audit_log_enabled(self.conn):
            self.users._audit(admin_id, target.user_id, "caller_id", old_value, new_value)
        return caller_ids

    def delete(self, target: UserAttributeTarget, *, admin_id: int) -> list[str]:
        self.conn.execute("LOCK TABLE caller_id_users IN SHARE ROW EXCLUSIVE MODE")
        rows = self.conn.execute(
            "SELECT caller_id FROM caller_id_users WHERE user_id = %s ORDER BY caller_id",
            (target.user_id,),
        ).fetchall()
        current = [str(row[0]) for row in rows]
        if not current:
            return []
        self.conn.execute("DELETE FROM caller_id_users WHERE user_id = %s", (target.user_id,))
        if is_user_audit_log_enabled(self.conn):
            self.users._audit(admin_id, target.user_id, "caller_id", ",".join(current), AUDIT_LOG_NOVALUE)
        return current
