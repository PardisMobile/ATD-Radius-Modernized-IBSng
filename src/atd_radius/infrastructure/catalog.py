from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg


@dataclass(frozen=True)
class CatalogRecord:
    id: UUID
    name: str
    description: str | None
    enabled: bool


class GroupRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(self, name: str, description: str = "", enabled: bool = True) -> CatalogRecord:
        row = self.conn.execute(
            "INSERT INTO groups (name, description, enabled) VALUES (%s,%s,%s) RETURNING id,name,description,enabled",
            (name.strip(), description.strip(), enabled),
        ).fetchone()
        assert row is not None
        return CatalogRecord(*row)

    def list(self, limit: int = 100, offset: int = 0) -> list[CatalogRecord]:
        rows = self.conn.execute(
            "SELECT id,name,description,enabled FROM groups ORDER BY name LIMIT %s OFFSET %s",
            (limit, offset),
        ).fetchall()
        return [CatalogRecord(*row) for row in rows]


class ServiceRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(self, name: str, description: str = "", enabled: bool = True) -> CatalogRecord:
        row = self.conn.execute(
            "INSERT INTO services (name, description, enabled) VALUES (%s,%s,%s) RETURNING id,name,description,enabled",
            (name.strip(), description.strip(), enabled),
        ).fetchone()
        assert row is not None
        return CatalogRecord(*row)

    def list(self, limit: int = 100, offset: int = 0) -> list[CatalogRecord]:
        rows = self.conn.execute(
            "SELECT id,name,description,enabled FROM services ORDER BY name LIMIT %s OFFSET %s",
            (limit, offset),
        ).fetchall()
        return [CatalogRecord(*row) for row in rows]
