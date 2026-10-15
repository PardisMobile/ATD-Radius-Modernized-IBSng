"""Orchestrate recurring VoIP limit checks without guessing provider behavior.

The caller supplies transaction-scoped planning and a source-backed termination
adapter. This keeps database transaction lifetime and provider-specific kill
semantics outside the timer worker.
"""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from threading import RLock

from atd_radius.application.voip_limit_scheduler import VoipLimitScheduler
from atd_radius.domain.accounting_charge import VoipLimitPlan


class VoipLimitCheckLoop:
    """Schedule A1.24-shaped per-user checks and execute per-session decisions.

    `check_limits` must resolve the user's currently active VoIP sessions,
    credit, rules and per-session RAS/port context in a fresh transaction, then
    return `VoipLimitPlan`. `terminate_session` must perform the configured,
    source-backed RAS action and preserve the supplied reason. This class does
    not substitute a generic RADIUS Disconnect for provider-specific behavior.
    """

    def __init__(
        self,
        scheduler: VoipLimitScheduler,
        check_limits: Callable[[int], VoipLimitPlan],
        terminate_session: Callable[[str, str], None],
        *,
        on_error: Callable[[int, Exception], None] | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.check_limits = check_limits
        self.terminate_session = terminate_session
        self.on_error = on_error
        self._lock = RLock()
        self._failures: dict[int, int] = {}

    @staticmethod
    def _key(user_id: int) -> tuple[str, int]:
        return ("voip-user", user_id)

    def start(self) -> None:
        self.scheduler.start()

    def schedule(self, user_id: int, delay_seconds: int | float | Decimal = 1) -> None:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        self.scheduler.schedule(self._key(user_id), delay_seconds, lambda: self._tick(user_id))

    def cancel(self, user_id: int) -> bool:
        with self._lock:
            self._failures.pop(user_id, None)
        return self.scheduler.cancel(self._key(user_id))

    def close(self) -> None:
        self.scheduler.close()

    def _tick(self, user_id: int) -> int | float | Decimal | None:
        try:
            plan = self.check_limits(user_id)
        except Exception as exc:
            with self._lock:
                failures = self._failures.get(user_id, 0) + 1
                self._failures[user_id] = failures
            if self.on_error is not None:
                self.on_error(user_id, exc)
            # Retry transient database/provider-state failures with bounded
            # backoff; a successful check resets this counter below.
            return min(2 ** min(failures, 6), 60)

        with self._lock:
            self._failures.pop(user_id, None)

        failed_terminations = False
        for unique_id, reason in plan.kill_reasons:
            try:
                self.terminate_session(unique_id, reason)
            except Exception as exc:
                failed_terminations = True
                if self.on_error is not None:
                    self.on_error(user_id, exc)

        if failed_terminations:
            # Re-read the active sessions and retry failed provider actions;
            # termination adapters must be idempotent for a session/reason pair.
            return 1
        if plan.remaining_seconds is None or plan.remaining_seconds <= 0:
            return None
        return plan.remaining_seconds
