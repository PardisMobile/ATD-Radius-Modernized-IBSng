"""Native IBSng A1.24 RAS persistence."""
from __future__ import annotations

from dataclasses import dataclass

from .ras_sql import (
    delete_ras_ippool,
    delete_ras_port,
    insert_ras_ippool,
    select_active_ras_ids,
    select_ras,
    select_ras_ippools,
    select_ras_ports,
    upsert_ras_port,
)


@dataclass(frozen=True, slots=True)
class RASRecord:
    ras_id: int
    description: str
    ip: str
    ras_type: str
    radius_secret: str
    active: bool
    comment: str | None


@dataclass(frozen=True, slots=True)
class RASPortRecord:
    ras_id: int
    port_name: str
    phone: str | None
    type: str | None
    comment: str | None


@dataclass(frozen=True, slots=True)
class RASIPPoolRecord:
    serial: int
    ras_id: int
    ippool_id: int


class RASRepository:
    """Persistence contract for the native A1.24 ras family of tables."""

    def __init__(self, conn, on_change=None) -> None:
        self.conn = conn
        self.on_change = on_change

    def _changed(self, ras_id: int) -> None:
        if self.on_change is not None:
            self.on_change(ras_id)

    def list(self) -> list[RASRecord]:
        rows = self.conn.execute(
            "SELECT ras_id, ras_description, ras_ip, ras_type, radius_secret, active, comment "
            "FROM ras ORDER BY ras_id"
        ).fetchall()
        return [self._ras(row) for row in rows]

    def active_ids(self) -> list[int]:
        return [int(row[0]) for row in self.conn.execute(select_active_ras_ids()).fetchall()]

    def get_by_ip(self, ip: str) -> RASRecord | None:
        row = self.conn.execute(
            "SELECT ras_id, ras_description, ras_ip, ras_type, radius_secret, active, comment "
            "FROM ras WHERE ras_ip=%s::inet",
            (ip,),
        ).fetchone()
        return self._ras(row) if row else None

    def get_secret_by_ip(self, ip: str) -> str | None:
        row = self.conn.execute("SELECT radius_secret FROM ras WHERE ras_ip=%s::inet AND active=true", (ip,)).fetchone()
        return str(row[0]) if row else None

    def get(self, ras_id: int) -> RASRecord | None:
        row = self.conn.execute(select_ras(ras_id)).fetchone()
        return self._ras(row) if row else None

    def create(
        self,
        description: str,
        ip: str,
        ras_type: str,
        radius_secret: str,
        active: bool = True,
        comment: str | None = None,
    ) -> RASRecord:
        ras_id = int(self.conn.execute("SELECT nextval('ras_id_seq')").fetchone()[0])
        self.conn.execute(
            "INSERT INTO ras (ras_id, ras_description, ras_ip, ras_type, radius_secret, active, comment) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (ras_id, description, ip, ras_type, radius_secret, active, comment),
        )
        record = RASRecord(ras_id, description, ip, ras_type, radius_secret, active, comment)
        self._changed(ras_id)
        return record

    def update(
        self,
        ras_id: int,
        description: str,
        ip: str,
        ras_type: str,
        radius_secret: str,
        active: bool,
        comment: str | None,
    ) -> RASRecord:
        if self.get(ras_id) is None:
            raise LookupError("RAS not found")
        self.conn.execute(
            "UPDATE ras SET ras_description=%s, ras_ip=%s, ras_type=%s, radius_secret=%s, active=%s, comment=%s "
            "WHERE ras_id=%s",
            (description, ip, ras_type, radius_secret, active, comment, ras_id),
        )
        record = RASRecord(ras_id, description, ip, ras_type, radius_secret, active, comment)
        self._changed(ras_id)
        return record

    def delete(self, ras_id: int) -> None:
        if self.get(ras_id) is None:
            raise LookupError("RAS not found")
        self.conn.execute("DELETE FROM ras_ippools WHERE ras_id=%s", (ras_id,))
        self.conn.execute("DELETE FROM ras_ports WHERE ras_id=%s", (ras_id,))
        self.conn.execute("DELETE FROM ras_attrs WHERE ras_id=%s", (ras_id,))
        self.conn.execute("DELETE FROM ras WHERE ras_id=%s", (ras_id,))
        self._changed(ras_id)

    def ports(self, ras_id: int) -> list[RASPortRecord]:
        rows = self.conn.execute(select_ras_ports(ras_id)).fetchall()
        return [RASPortRecord(int(r[0]), r[1], r[2], r[3], r[4]) for r in rows]

    def upsert_port(self, ras_id: int, port_name: str, phone: str | None, port_type: str | None, comment: str | None) -> None:
        self.conn.execute(upsert_ras_port(), (ras_id, port_name, phone, port_type, comment))
        self._changed(ras_id)

    def delete_port(self, ras_id: int, port_name: str) -> None:
        self.conn.execute(delete_ras_port(), (ras_id, port_name))
        self._changed(ras_id)

    def attributes(self, ras_id: int) -> list[tuple[str, str]]:
        rows = self.conn.execute(
            "SELECT ras_id, attr_name, attr_value FROM ras_attrs WHERE ras_id=%s ORDER BY attr_name",
            (ras_id,),
        ).fetchall()
        return [(r[1], r[2]) for r in rows]

    def set_attribute(self, ras_id: int, name: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO ras_attrs (ras_id, attr_name, attr_value) VALUES (%s,%s,%s) "
            "ON CONFLICT (ras_id, attr_name) DO UPDATE SET attr_value=EXCLUDED.attr_value",
            (ras_id, name, value),
        )
        self._changed(ras_id)

    def delete_attribute(self, ras_id: int, name: str) -> None:
        self.conn.execute("DELETE FROM ras_attrs WHERE ras_id=%s AND attr_name=%s", (ras_id, name))
        self._changed(ras_id)

    def ippools(self, ras_id: int) -> list[RASIPPoolRecord]:
        rows = self.conn.execute(select_ras_ippools(ras_id)).fetchall()
        return [RASIPPoolRecord(int(r[0]), int(r[1]), int(r[2])) for r in rows]

    def add_ippool(self, ras_id: int, ippool_id: int) -> int:
        row = self.conn.execute(insert_ras_ippool(), (ras_id, ippool_id)).fetchone()
        serial = int(row[0])
        self._changed(ras_id)
        return serial

    def delete_ippool(self, serial: int) -> None:
        self.conn.execute(delete_ras_ippool(), (serial,))
        row = self.conn.execute("SELECT ras_id FROM ras_ippools WHERE serial=%s", (serial,)).fetchone()
        if row is not None:
            self._changed(int(row[0]))

    @staticmethod
    def _ras(row) -> RASRecord:
        return RASRecord(int(row[0]), row[1], str(row[2]), row[3], row[4], bool(row[5]), row[6])
