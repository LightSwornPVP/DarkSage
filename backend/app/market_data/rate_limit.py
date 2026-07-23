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
    """Enforces a minimum interval between successive ``acquire()`` calls.

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

    async def acquire(self) -> None:
        now = self._clock()
        if self._last_acquired_at is not None:
            wait_for = self._min_interval_seconds - (now - self._last_acquired_at)
            if wait_for > 0:
                await self._sleep(wait_for)
        self._last_acquired_at = self._clock()
