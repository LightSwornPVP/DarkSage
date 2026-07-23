"""Tests for IntervalRateLimiter using a fake clock/sleep (no real timing)."""

from __future__ import annotations

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
