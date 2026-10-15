"""Thread-safe one-shot scheduler for source-shaped VoIP limit checks.

The scheduler owns timer lifecycle only. A callback must open its own database
transaction, recompute the current limit plan, execute any supported RAS action,
and return the next delay. It deliberately does not infer provider termination
semantics from RAS metadata.
"""
from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from decimal import Decimal
from threading import Condition, Thread
from time import monotonic
from typing import TypeAlias

Delay: TypeAlias = int | float | Decimal
LimitCallback: TypeAlias = Callable[[], Delay | None]


@dataclass(frozen=True, slots=True)
class _Scheduled:
    deadline: float
    generation: int
    callback: LimitCallback


class VoipLimitScheduler:
    """Single-worker, per-key rescheduling loop with cancellation generations.

    Each key has at most one pending invocation. Callbacks run outside the
    condition lock. Replacing/cancelling a key while its callback is running
    prevents the old callback result from overwriting the newer schedule.
    """

    MIN_DELAY_SECONDS = 1.0
    MAX_DELAY_SECONDS = float(7 * 24 * 3600)

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        on_error: Callable[[Hashable, Exception], None] | None = None,
        name: str = "atd-voip-limits",
    ) -> None:
        self._clock = clock
        self._on_error = on_error
        self._name = name
        self._condition = Condition()
        self._pending: dict[Hashable, _Scheduled] = {}
        self._generations: dict[Hashable, int] = {}
        self._thread: Thread | None = None
        self._closed = False

    @classmethod
    def _delay(cls, value: Delay) -> float:
        delay = float(value)
        if delay != delay or delay in (float("inf"), float("-inf")):
            raise ValueError("VoIP limit delay must be finite")
        if delay <= 0:
            raise ValueError("VoIP limit delay must be positive")
        return min(max(delay, cls.MIN_DELAY_SECONDS), cls.MAX_DELAY_SECONDS)

    def start(self) -> None:
        """Start the worker once; repeated calls are harmless."""
        with self._condition:
            if self._closed:
                raise RuntimeError("VoIP limit scheduler is closed")
            if self._thread is not None:
                return
            self._thread = Thread(target=self._run, name=self._name, daemon=True)
            self._thread.start()

    def schedule(self, key: Hashable, delay_seconds: Delay, callback: LimitCallback) -> None:
        delay = self._delay(delay_seconds)
        with self._condition:
            if self._closed:
                raise RuntimeError("VoIP limit scheduler is closed")
            generation = self._generations.get(key, 0) + 1
            self._generations[key] = generation
            self._pending[key] = _Scheduled(self._clock() + delay, generation, callback)
            self._condition.notify_all()

    def cancel(self, key: Hashable) -> bool:
        """Cancel a pending key and invalidate a callback currently in flight."""
        with self._condition:
            existed = key in self._pending
            self._pending.pop(key, None)
            self._generations[key] = self._generations.get(key, 0) + 1
            self._condition.notify_all()
            return existed

    def close(self, *, wait: bool = True) -> None:
        with self._condition:
            self._closed = True
            self._pending.clear()
            self._condition.notify_all()
            thread = self._thread
        if wait and thread is not None and thread is not __import__("threading").current_thread():
            thread.join()

    def pending_keys(self) -> tuple[Hashable, ...]:
        with self._condition:
            return tuple(self._pending)

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._closed and not self._pending:
                    self._condition.wait()
                if self._closed:
                    return
                key, item = min(self._pending.items(), key=lambda pair: pair[1].deadline)
                remaining = item.deadline - self._clock()
                if remaining > 0:
                    self._condition.wait(remaining)
                    continue
                if self._pending.get(key) != item:
                    continue
                self._pending.pop(key, None)

            try:
                next_delay = item.callback()
                if next_delay is not None:
                    delay = self._delay(next_delay)
                    with self._condition:
                        if (
                            not self._closed
                            and self._generations.get(key) == item.generation
                            and key not in self._pending
                        ):
                            self._pending[key] = _Scheduled(
                                self._clock() + delay, item.generation, item.callback
                            )
                            self._condition.notify_all()
            except Exception as exc:
                if self._on_error is not None:
                    try:
                        self._on_error(key, exc)
                    except Exception:
                        # An error reporter must not terminate the scheduler worker.
                        pass
