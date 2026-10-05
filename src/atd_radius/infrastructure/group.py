"""PostgreSQL persistence mapped directly to IBSng A1.24 groups."""
from __future__ import annotations

from dataclasses import dataclass

import psycopg

from .group_sql import DELETE_GROUP, DELETE_GROUP_ATTR, GROUP, GROUP_ATTRS, INSERT_GROUP, LIST_GROUPS, UPDATE_GROUP, UPSERT_GROUP_ATTR


@dataclass(frozen=True, slots=True)
class GroupRecord:
    id: int
    name: str
    owner_id: int | None
    comment: str | None


@dataclass(frozen=True, slots=True)
class GroupAttribute:
    name: str
    value: str


class GroupRepository:
    """Repository for the native A1.24 groups and group_attrs tables."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(self, name: str, comment: str | None, owner_id: int) -> GroupRecord:
        self._validate_name(name)
        group_id = int(self.conn.execute("SELECT nextval('groups_group_id_seq')").fetchone()[0])
        self.conn.execute(INSERT_GROUP, (group_id, name, comment, owner_id))
        return GroupRecord(group_id, name, owner_id, comment)

    def list(self) -> list[GroupRecord]:
        rows = self.conn.execute(LIST_GROUPS.replace("ORDER BY group_id", "ORDER BY group_name DESC")).fetchall()
        return [self._record(row) for row in rows]

    def get(self, group_id: int) -> GroupRecord | None:
        row = self.conn.execute(GROUP, (group_id,)).fetchone()
        return self._record(row) if row else None

    def get_by_name(self, name: str) -> GroupRecord | None:
        row = self.conn.execute(
            "SELECT group_id, group_name, owner_id, comment FROM groups WHERE group_name=%s",
            (name,),
        ).fetchone()
        return self._record(row) if row else None

    def update(self, group_id: int, name: str, comment: str | None, owner_id: int) -> GroupRecord:
        self._validate_name(name)
        current = self.get(group_id)
        if current is None:
            raise LookupError("group not found")
        if current.name != name and self.get_by_name(name) is not None:
            raise ValueError("group name already exists")
        self.conn.execute(UPDATE_GROUP, (group_id, name, owner_id, comment))
        return GroupRecord(group_id, name, owner_id, comment)

    def delete(self, group_id: int) -> None:
        current = self.get(group_id)
        if current is None:
            raise LookupError("group not found")
        row = self.conn.execute("SELECT user_id FROM users WHERE group_id=%s ORDER BY user_id", (group_id,)).fetchall()
        if row:
            raise ValueError("group is used by users")
        self.conn.execute(DELETE_GROUP_ATTR, (group_id,))
        self.conn.execute(DELETE_GROUP, (group_id,))

    def attributes(self, group_id: int) -> list[GroupAttribute]:
        rows = self.conn.execute(GROUP_ATTRS, (group_id,)).fetchall()
        return [GroupAttribute(name=row[1], value=row[2]) for row in rows]

    def set_attribute(self, group_id: int, name: str, value: str) -> None:
        self.conn.execute(UPSERT_GROUP_ATTR, (group_id, name, value))

    def delete_attribute(self, group_id: int, name: str) -> None:
        self.conn.execute(DELETE_GROUP_ATTR, (group_id, name))

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in name):
            raise ValueError("invalid group name")

    @staticmethod
    def _record(row: tuple) -> GroupRecord:
        return GroupRecord(id=int(row[0]), name=row[1], owner_id=row[2], comment=row[3])
