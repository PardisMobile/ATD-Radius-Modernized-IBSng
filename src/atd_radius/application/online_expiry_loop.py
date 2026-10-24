"""Enforce A1.24 absolute and relative expiry against live sessions."""
from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
from typing import Callable
from atd_radius.application.voip_limit_scheduler import VoipLimitScheduler
from atd_radius.domain.radius_runtime import SessionKey
from atd_radius.infrastructure.ras_termination import PermanentRASTerminationError

@dataclass(frozen=True, slots=True)
class OnlineExpiryPlan:
    remaining_seconds: float | None
    kill_reasons: tuple[tuple[SessionKey, str], ...] = ()

def nearest_expiration(attributes: dict[str, str], now: float) -> tuple[int | None, float | None]:
    """Return A1.24 nearest_exp_date_epoch and time_to_nearest_exp_date."""
    deadlines: list[float] = []
    raw_absolute = attributes.get("abs_exp_date")
    if raw_absolute not in (None, ""):
        try: deadlines.append(float(raw_absolute))
        except (TypeError, ValueError): pass
    raw_duration, raw_first_login = attributes.get("rel_exp_date"), attributes.get("first_login")
    if raw_duration not in (None, "") and raw_first_login not in (None, ""):
        try:
            duration, first_login = float(raw_duration), float(raw_first_login)
            if duration >= 0: deadlines.append(first_login + duration)
        except (TypeError, ValueError): pass
    if not deadlines:
        return None, None
    deadline = min(deadlines)
    return int(deadline), deadline - now


def plan_online_expiry(attributes: dict[str, str], sessions: tuple[SessionKey, ...], now: float) -> OnlineExpiryPlan:
    """Calculate the earliest native A1.24 user-expiry deadline."""
    if not sessions:
        return OnlineExpiryPlan(None)
    deadlines: list[tuple[float, str]] = []
    raw_absolute = attributes.get("abs_exp_date")
    if raw_absolute not in (None, ""):
        try: deadlines.append((float(raw_absolute), "absolute_expired"))
        except (TypeError, ValueError): pass
    raw_duration, raw_first_login = attributes.get("rel_exp_date"), attributes.get("first_login")
    if raw_duration not in (None, "") and raw_first_login not in (None, ""):
        try:
            duration, first_login = float(raw_duration), float(raw_first_login)
            if duration >= 0: deadlines.append((first_login + duration, "relative_expired"))
        except (TypeError, ValueError): pass
    if not deadlines: return OnlineExpiryPlan(None)
    deadline, reason = min(deadlines, key=lambda item: item[0])
    remaining = deadline - now
    if remaining > 0: return OnlineExpiryPlan(remaining)
    return OnlineExpiryPlan(0, tuple((key, reason) for key in sessions))

class OnlineSessionExpiryLoop:
    """Schedule source-compatible expiry checks and terminate every live instance."""
    def __init__(self, scheduler: VoipLimitScheduler, check_user: Callable[[int], OnlineExpiryPlan],
                 terminate_session: Callable[[SessionKey, str], None],
                 *, on_error: Callable[[int, Exception], None] | None = None) -> None:
        self.scheduler, self.check_user, self.terminate_session, self.on_error = scheduler, check_user, terminate_session, on_error
        self._lock = RLock()
        self._failures: dict[int, int] = {}
        self._termination_failures: dict[tuple[int, SessionKey], int] = {}
    @staticmethod
    def _key(user_id: int) -> tuple[str, int]: return ("online-expiry-user", user_id)
    def start(self) -> None: self.scheduler.start()
    def schedule(self, user_id: int, delay_seconds: int | float = 1) -> None:
        if user_id <= 0: raise ValueError("user_id must be positive")
        self.scheduler.schedule(self._key(user_id), delay_seconds, lambda: self._tick(user_id))
    def cancel(self, user_id: int) -> bool:
        with self._lock:
            self._failures.pop(user_id, None)
            for key in tuple(self._termination_failures):
                if key[0] == user_id: self._termination_failures.pop(key, None)
        return self.scheduler.cancel(self._key(user_id))
    def close(self) -> None: self.scheduler.close()
    def _report_error(self, user_id: int, exc: Exception) -> None:
        if self.on_error is not None:
            try: self.on_error(user_id, exc)
            except Exception: pass
    def _tick(self, user_id: int):
        try: plan = self.check_user(user_id)
        except Exception as exc:
            with self._lock:
                failures = self._failures.get(user_id, 0) + 1
                self._failures[user_id] = failures
            self._report_error(user_id, exc)
            return min(2 ** min(failures, 6), 60)
        with self._lock: self._failures.pop(user_id, None)
        retry_delay = 0
        for session_key, reason in plan.kill_reasons:
            failure_key = (user_id, session_key)
            try:
                self.terminate_session(session_key, reason)
                with self._lock: self._termination_failures.pop(failure_key, None)
            except PermanentRASTerminationError as exc:
                with self._lock: self._termination_failures.pop(failure_key, None)
                self._report_error(user_id, exc)
            except Exception as exc:
                with self._lock:
                    failures = self._termination_failures.get(failure_key, 0) + 1
                    self._termination_failures[failure_key] = failures
                retry_delay = max(retry_delay, min(2 ** min(failures, 6), 60))
                self._report_error(user_id, exc)
        if retry_delay: return retry_delay
        if plan.kill_reasons or plan.remaining_seconds is None or plan.remaining_seconds <= 0: return None
        return plan.remaining_seconds
