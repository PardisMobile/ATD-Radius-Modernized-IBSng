"""Native A1.24 accounting persistence adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

from atd_radius.infrastructure.connection_log import ConnectionLog
from atd_radius.infrastructure.connection_log_repository import ConnectionLogRepository


class NativeAccountingPersistence:
    """Translate RADIUS accounting events into native connection_log records."""

    def __init__(self, repository: ConnectionLogRepository, clock: callable | None = None) -> None:
        self.repository = repository
        self.clock = clock or datetime.now

    @staticmethod
    def _details(event) -> dict[str, str]:
        details = dict(event.attributes)
        if event.session_id:
            details.setdefault("Acct-Session-Id", event.session_id)
        if event.remote_ip:
            details.setdefault("Framed-IP-Address", event.remote_ip)
        return details

    def start(self, event, user_id: int, ras_id: int) -> int:
        record = ConnectionLog(
            connection_log_id=0,
            user_id=user_id,
            credit_used=None,
            login_time=self.clock(),
            logout_time=None,
            successful=True,
            service=1,
            ras_id=ras_id,
            details=self._details(event),
        )
        return self.repository.create(record)

    def update(self, connection_log_id: int, event) -> None:
        for name, value in self._details(event).items():
            self.repository.add_detail(connection_log_id, name, value)

    def stop(self, connection_log_id: int, event) -> None:
        for name, value in self._details(event).items():
            self.repository.add_detail(connection_log_id, name, value)
        self.repository.close(connection_log_id, self.clock(), None, True)
