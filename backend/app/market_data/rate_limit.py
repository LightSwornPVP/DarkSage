"""Rate-limit abstraction for market-data provider adapters.

Provider-independent: any concrete provider can be given a rate limiter
appropriate to its vendor's quota, without callers or the abstraction itself
knowing which vendor is involved (ARCHITECTURE.md Section 7).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol


class RateLimiter(Protocol):
    """Something a provider adapter can await before making a request."""

    async def acquire(self) -> None: ...


class IntervalRateLimiter:
    """Enforces a minimum interval between successive ``acquire()`` calls,
    safely under concurrent async callers.

    An internal lock serializes ``acquire()`` end-to-end (read last-acquired
    time, sleep if needed, record the new last-acquired time) so concurrent
    callers cannot both observe the same "it's been long enough" state and
    pass through together. The lock is only ever held inside ``acquire()``
    and never awaits anything that could re-enter it, so it cannot deadlock;
    ``async with`` releases it even if ``sleep`` raises or the caller is
    cancelled, so one failed caller never permanently blocks the rest.

    ``clock``/``sleep`` are injectable so tests can verify throttling
    behavior deterministically, without real wall-clock delays.
    """

    def __init__(
        self,
        min_interval_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be >= 0")
        self._min_interval_seconds = min_interval_seconds
        self._clock = clock
        self._sleep = sleep
        self._last_acquired_at: float | None = None
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            if self._last_acquired_at is not None:
                wait_for = self._min_interval_seconds - (now - self._last_acquired_at)
                if wait_for > 0:
                    await self._sleep(wait_for)
            self._last_acquired_at = self._clock()
