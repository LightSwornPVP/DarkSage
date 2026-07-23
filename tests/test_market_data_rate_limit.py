"""Tests for IntervalRateLimiter using a fake clock/sleep (no real timing)."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.market_data.rate_limit import IntervalRateLimiter


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


async def test_first_acquire_never_sleeps() -> None:
    clock = _FakeClock(100.0)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    limiter = IntervalRateLimiter(1.0, clock=clock, sleep=fake_sleep)
    await limiter.acquire()
    assert sleeps == []


async def test_acquire_sleeps_when_called_too_soon() -> None:
    clock = _FakeClock(0.0)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    limiter = IntervalRateLimiter(1.0, clock=clock, sleep=fake_sleep)
    await limiter.acquire()
    clock.now += 0.2  # only 0.2s elapsed, need 1.0s
    await limiter.acquire()
    assert sleeps == [0.8]


async def test_acquire_does_not_sleep_after_interval_elapsed() -> None:
    clock = _FakeClock(0.0)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    limiter = IntervalRateLimiter(1.0, clock=clock, sleep=fake_sleep)
    await limiter.acquire()
    clock.now += 2.0  # plenty of time has passed
    await limiter.acquire()
    assert sleeps == []


# --- Concurrency safety (blocker 3) ---


async def test_concurrent_acquires_are_serialized_and_spaced() -> None:
    clock = _FakeClock(0.0)
    sleep_durations: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        start = clock.now  # snapshot before yielding, to expose a stale-read race
        sleep_durations.append(seconds)
        await asyncio.sleep(0)  # yield control — where an unlocked caller could interleave
        clock.now = start + seconds

    limiter = IntervalRateLimiter(1.0, clock=clock, sleep=fake_sleep)
    await limiter.acquire()  # baseline: last-acquired = 0.0, no sleep needed

    await asyncio.gather(limiter.acquire(), limiter.acquire())

    assert sleep_durations == [1.0, 1.0]
    # Properly serialized and spaced: 0.0 -> 1.0 -> 2.0. Without the lock,
    # both concurrent callers would read the same stale last-acquired time
    # and collapse onto the same instant (1.0) instead of being spaced apart.
    assert clock.now == 2.0


async def test_acquire_lock_is_released_after_sleep_failure() -> None:
    clock = _FakeClock(0.0)
    call_count = 0

    async def flaky_sleep(seconds: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated transient failure")
        clock.now += seconds

    limiter = IntervalRateLimiter(1.0, clock=clock, sleep=flaky_sleep)
    await limiter.acquire()  # baseline: no sleep needed

    with pytest.raises(RuntimeError):
        await limiter.acquire()  # needs to sleep -> flaky_sleep fails

    # The lock must have been released despite the failure — this must
    # complete promptly rather than hang forever on a permanently held lock.
    await asyncio.wait_for(limiter.acquire(), timeout=1.0)
