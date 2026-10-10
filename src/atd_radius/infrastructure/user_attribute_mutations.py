"""Source-derived mutation slice for generic IBSng A1.24 user attributes.

Only source-traced handlers with generic persistence are enabled. Values with
source-side validation are normalized by their corresponding handler contract;
other specialized attributes remain blocked.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


USER_ATTRIBUTE_UPDATER_HANDLERS = {
    "name": "comment.NameAttrUpdater",
    "comment": "comment.CommentAttrUpdater",
    "phone": "comment.PhoneAttrUpdater",
    "lock": "lock.LockAttrUpdater",
    "multi_login": "multilogin.MultiLoginAttrUpdater",
    "session_timeout": "session_timeout.SessionTimeoutAttrUpdater",
    "idle_timeout": "idle_timeout.IdleTimeoutAttrUpdater",
    "voip_preferred_language": "voip_preferred_language.VoIPPreferredLanguageAttrUpdater",
    "save_bw_usage": "save_bw_usage.SaveBWUsageAttrUpdater",
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
    owner_username: str | None


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
            SELECT u.user_id, nu.normal_username, u.owner_id, owner.username
            FROM users u
            JOIN normal_users nu ON nu.user_id = u.user_id
            LEFT JOIN admins owner ON owner.admin_id = u.owner_id
            WHERE nu.normal_username = %s
            FOR UPDATE OF u
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None
        return UserAttributeTarget(
            int(row[0]), str(row[1]), row[2], str(row[3]) if row[3] is not None else None
        )

    @staticmethod
    def normalize(attrs: dict[str, str], to_delete: list[str]) -> dict[str, str]:
        unknown = (set(attrs) | set(to_delete)) - set(USER_ATTRIBUTE_UPDATER_HANDLERS)
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

        normalized = dict(attrs)
        if "save_bw_usage" in normalized and normalized["save_bw_usage"] != "":
            raise UserAttributeMutationError("save_bw_usage is a marker attribute and must have an empty value")
        for name in ("multi_login", "session_timeout", "idle_timeout"):
            if name not in normalized:
                continue
            try:
                value = int(normalized[name])
            except ValueError as exc:
                raise UserAttributeMutationError(
                    f"{name}: expected an integer"
                ) from exc
            if name == "multi_login" and not 0 <= value <= 255:
                raise UserAttributeMutationError(
                    "multi_login: expected an integer from 0 to 255"
                )
            normalized[name] = str(value)
        return normalized

    def apply(
        self,
        target: UserAttributeTarget,
        *,
        admin_id: int,
        attrs: dict[str, str],
        to_delete: list[str],
    ) -> MutatedUserAttributes:
        attrs = self.normalize(attrs, to_delete)
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


    def change_owner(
        self,
        target: UserAttributeTarget,
        *,
        admin_id: int,
        owner_username: str,
    ) -> str:
        """Implement A1.24 owner_name's special updater, not user_attrs storage."""
        owner_row = self.conn.execute(
            "SELECT admin_id, username FROM admins WHERE username = %s FOR SHARE",
            (owner_username,),
        ).fetchone()
        if owner_row is None:
            raise LookupError("owner administrator not found")
        if target.owner_username is None:
            raise RuntimeError("current user owner does not resolve to an administrator")

        new_owner_id = int(owner_row[0])
        new_owner_name = str(owner_row[1])
        self.conn.execute(
            "UPDATE users SET owner_id = %s WHERE user_id = %s",
            (new_owner_id, target.user_id),
        )
        if target.owner_username != new_owner_name and is_user_audit_log_enabled(self.conn):
            self._audit(
                admin_id, target.user_id, "owner", target.owner_username, new_owner_name
            )
        return new_owner_name

    def change_group(
        self,
        target: UserAttributeTarget,
        *,
        admin_id: int,
        group_id: int,
        group_name: str,
    ) -> str:
        """Apply A1.24 group_name updater semantics without storing it in user_attrs."""
        row = self.conn.execute(
            """
            SELECT g.group_name
            FROM users u
            JOIN groups g ON g.group_id = u.group_id
            WHERE u.user_id = %s
            """,
            (target.user_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("current user group does not resolve to a group")
        previous_group_name = str(row[0])
        self.conn.execute(
            "UPDATE users SET group_id = %s WHERE user_id = %s",
            (group_id, target.user_id),
        )
        if is_user_audit_log_enabled(self.conn):
            self._audit(
                admin_id,
                target.user_id,
                "group",
                previous_group_name,
                group_name,
            )
        return previous_group_name

    def _audit(
        self, admin_id: int, user_id: int, name: str, old_value: str, new_value: str
    ) -> None:
        self.conn.execute(
            """
            SELECT insert_user_audit_log(%s, TRUE, %s, %s, %s, %s)
            """,
            (admin_id, user_id, name, old_value, new_value),
        )
