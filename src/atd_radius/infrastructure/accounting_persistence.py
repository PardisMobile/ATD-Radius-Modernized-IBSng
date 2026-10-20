"""Native A1.24 accounting persistence adapter."""
from __future__ import annotations

from datetime import datetime
from collections.abc import Callable
from atd_radius.infrastructure.connection_log import ConnectionLog
from atd_radius.infrastructure.connection_log_repository import ConnectionLogRepository


class NativeAccountingPersistence:
    """Translate RADIUS accounting events into native connection_log records."""

    def __init__(self, repository: ConnectionLogRepository, clock: Callable[[], datetime] | None = None) -> None:
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

    @staticmethod
    def _ras_time(attributes: dict[str, str], name: str) -> datetime | None:
        """Convert A1.24's provider-normalized epoch timestamp to local DB time."""
        value = attributes.get(name)
        if value in (None, ""):
            return None
        try:
            return datetime.fromtimestamp(float(value))
        except (TypeError, ValueError, OverflowError, OSError):
            return None

    def start(self, event, user_id: int, ras_id: int) -> int:
        # VoipUser.logToConnectionLog stores getCallStartTime(), which prefers
        # the RAS connect_time normalized by VoipRAS.setH323TimeInAttrs.
        login_time = self._ras_time(event.attributes, "connect_time") or self.clock()
        record = ConnectionLog(
            connection_log_id=0,
            user_id=user_id,
            credit_used=None,
            login_time=login_time,
            logout_time=None,
            successful=True,
            # A1.24 connection_log uses service=1 for Internet and service=2 for VoIP.
            service=2 if getattr(event, "service", "internet") == "voip" else 1,
            ras_id=ras_id,
            details=self._details(event),
        )
        return self.repository.create(record)

    def update(self, connection_log_id: int, event) -> None:
        for name, value in self._details(event).items():
            self.repository.upsert_detail(connection_log_id, name, value)

    def discard(self, connection_log_id: int) -> None:
        """Remove an early-opened log if the source RAS suppresses session history."""
        self.repository.delete(connection_log_id)

    def stop(self, connection_log_id: int, event, credit_used=None) -> None
        for name, value in self._details(event).items():
            self.repository.upsert_detail(connection_log_id, name, value)
        # VoipUser.logout sets call_end_time from RAS disconnect_time before
        # writing the native connection log. Keep that timestamp even when no
        # charging policy produced a credit_used value.
        logout_time = self._ras_time(event.attributes, "disconnect_time")
        if logout_time is None:
            logout_time = event.observed_at if credit_used is not None else self.clock()
        self.repository.close(
            connection_log_id,
            logout_time,
            str(credit_used) if credit_used is not None else None,
            True,
        )
