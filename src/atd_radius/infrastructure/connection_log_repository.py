"""Native PostgreSQL persistence for A1.24 connection_log records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import psycopg

from atd_radius.infrastructure.connection_log import ConnectionLog


@dataclass(frozen=True, slots=True)
class ConnectionLogRepository:
    """Persist connection_log and connection_log_details using the native schema."""

    conn: psycopg.Connection

    def create(self, record: ConnectionLog) -> int:
        connection_log_id = int(
            self.conn.execute("SELECT nextval('connection_log_id')").fetchone()[0]
        )
        self.conn.execute(
            """
            INSERT INTO connection_log
                (connection_log_id, user_id, credit_used, login_time, logout_time,
                 successful, service, ras_id)
            VALUES (%s, %s, %s::numeric, %s::timestamp, %s::timestamp,
                    %s, %s::smallint, %s)
            """,
            (
                connection_log_id,
                record.user_id,
                record.credit_used,
                record.login_time,
                record.logout_time,
                record.successful,
                record.service,
                record.ras_id,
            ),
        )
        if record.details:
            self.add_details(connection_log_id, record.details.items())
        return connection_log_id

    def add_detail(self, connection_log_id: int, name: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO connection_log_details(connection_log_id, name, value)
            VALUES (%s, %s, %s)
            """,
            (connection_log_id, name, value),
        )

    def add_details(self, connection_log_id: int, details: Iterable[tuple[str, str]]) -> None:
        for name, value in details:
            self.add_detail(connection_log_id, name, value)

    def upsert_detail(self, connection_log_id: int, name: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO connection_log_details(connection_log_id, name, value)
            VALUES (%s, %s, %s)
            ON CONFLICT (connection_log_id, name)
            DO UPDATE SET value=EXCLUDED.value
            """,
            (connection_log_id, name, value),
        )

    def close(
        self,
        connection_log_id: int,
        logout_time: datetime,
        credit_used: str | None,
        successful: bool | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE connection_log
            SET logout_time=%s, credit_used=%s::numeric, successful=%s
            WHERE connection_log_id=%s
            """,
            (logout_time, credit_used, successful, connection_log_id),
        )

    def get(self, connection_log_id: int) -> ConnectionLog | None:
        row = self.conn.execute(
            """
            SELECT connection_log_id, user_id, credit_used::text, login_time,
                   logout_time, successful, service, ras_id
            FROM connection_log
            WHERE connection_log_id=%s
            """,
            (connection_log_id,),
        ).fetchone()
        if row is None:
            return None
        details = self.conn.execute(
            """
            SELECT name, value
            FROM connection_log_details
            WHERE connection_log_id=%s
            ORDER BY name
            """,
            (connection_log_id,),
        ).fetchall()
        return ConnectionLog(
            connection_log_id=int(row[0]),
            user_id=int(row[1]) if row[1] is not None else None,
            credit_used=str(row[2]) if row[2] is not None else None,
            login_time=row[3],
            logout_time=row[4],
            successful=bool(row[5]),
            service=int(row[6]),
            ras_id=int(row[7]) if row[7] is not None else None,
            details={str(name): str(value) for name, value in details},
        )
