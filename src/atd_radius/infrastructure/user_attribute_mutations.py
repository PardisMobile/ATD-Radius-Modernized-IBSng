"""Source-derived mutation slice for generic IBSng A1.24 user attributes.

Only the simple comment plugin family is enabled here. Specialized attributes
must be implemented through their own handler contract, never written through
this generic persistence path.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


GENERIC_USER_ATTRIBUTE_HANDLERS = {
    "name": "comment.NameAttrUpdater",
    "comment": "comment.CommentAttrUpdater",
    "phone": "comment.PhoneAttrUpdater",
}
AUDIT_LOG_NOVALUE = "_NOVALUE_"
_INTEGER_FLAG = re.compile(r"I([01])\s*\.")


class UserAttributeMutationError(ValueError):
    """An unsupported or invalid A1.24 user-attribute mutation."""


class UserAttributeConnection(Protocol):
    def execute(self, sql: str, params=()): ...


@dataclass(frozen=True, slots=True)
class UserAttributeTarget:
    user_id: int
    username: str
    owner_id: int | None


@dataclass(frozen=True, slots=True)
class MutatedUserAttributes:
    user_id: int
    username: str
    attributes: list[tuple[str, str]]


def is_user_audit_log_enabled(conn: UserAttributeConnection) -> bool:
    """Parse the native protocol-0 integer flag without unpickling DB data.

    A1.24 defaults USER_AUDIT_LOG to enabled; a missing row therefore uses 1.
    """
    row = conn.execute(
        "SELECT value FROM defs WHERE name = %s",
        ("USER_AUDIT_LOG",),
    ).fetchone()
    if row is None:
        return True
    match = _INTEGER_FLAG.fullmatch(str(row[0]))
    if match is None:
        raise RuntimeError("invalid serialized USER_AUDIT_LOG definition")
    return match.group(1) == "1"


class UserAttributeMutationRepository:
    """Apply the verified generic A1.24 attribute-updater behavior."""

    def __init__(self, conn: UserAttributeConnection) -> None:
        self.conn = conn

    def lock_target(self, username: str) -> UserAttributeTarget | None:
        row = self.conn.execute(
            """
            SELECT u.user_id, nu.normal_username, u.owner_id
            FROM users u
            JOIN normal_users nu ON nu.user_id = u.user_id
            WHERE nu.normal_username = %s
            FOR UPDATE OF u
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None
        return UserAttributeTarget(int(row[0]), str(row[1]), row[2])

    @staticmethod
    def validate(attrs: dict[str, str], to_delete: list[str]) -> None:
        unknown = (set(attrs) | set(to_delete)) - set(GENERIC_USER_ATTRIBUTE_HANDLERS)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise UserAttributeMutationError(
                f"attribute requires its specialized A1.24 handler: {names}"
            )
        if any(not isinstance(name, str) or not name for name in attrs):
            raise UserAttributeMutationError("attribute names must be non-empty strings")
        if any(not isinstance(value, str) for value in attrs.values()):
            raise UserAttributeMutationError("attribute values must be strings")
        if len(set(to_delete)) != len(to_delete):
            raise UserAttributeMutationError("duplicate attributes in to_delete")
        overlap = set(attrs) & set(to_delete)
        if overlap:
            raise UserAttributeMutationError(
                "an attribute cannot be changed and deleted in the same request"
            )

    def apply(
        self,
        target: UserAttributeTarget,
        *,
        admin_id: int,
        attrs: dict[str, str],
        to_delete: list[str],
    ) -> MutatedUserAttributes:
        self.validate(attrs, to_delete)
        names = sorted(set(attrs) | set(to_delete))
        current: dict[str, str] = {}
        if names:
            rows = self.conn.execute(
                """
                SELECT attr_name, attr_value
                FROM user_attrs
                WHERE user_id = %s AND attr_name = ANY(%s)
                """,
                (target.user_id, names),
            ).fetchall()
            current = {str(name): str(value) for name, value in rows}

        audit_enabled = is_user_audit_log_enabled(self.conn)
        for name, value in attrs.items():
            old_value = current.get(name, AUDIT_LOG_NOVALUE)
            if name in current:
                self.conn.execute(
                    """
                    UPDATE user_attrs SET attr_value = %s
                    WHERE user_id = %s AND attr_name = %s
                    """,
                    (value, target.user_id, name),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO user_attrs (user_id, attr_name, attr_value)
                    VALUES (%s, %s, %s)
                    """,
                    (target.user_id, name, value),
                )
            if audit_enabled and old_value != value:
                self._audit(admin_id, target.user_id, name, old_value, value)

        for name in to_delete:
            if name not in current:
                continue
            self.conn.execute(
                "DELETE FROM user_attrs WHERE user_id = %s AND attr_name = %s",
                (target.user_id, name),
            )
            if audit_enabled:
                self._audit(
                    admin_id, target.user_id, name, current[name], AUDIT_LOG_NOVALUE
                )

        rows = self.conn.execute(
            "SELECT attr_name, attr_value FROM user_attrs WHERE user_id = %s ORDER BY attr_name",
            (target.user_id,),
        ).fetchall()
        return MutatedUserAttributes(
            target.user_id,
            target.username,
            [(str(name), str(value)) for name, value in rows],
        )

    def _audit(
        self, admin_id: int, user_id: int, name: str, old_value: str, new_value: str
    ) -> None:
        self.conn.execute(
            """
            SELECT insert_user_audit_log(%s, TRUE, %s, %s, %s, %s)
            """,
            (admin_id, user_id, name, old_value, new_value),
        )
