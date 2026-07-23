"""Tests for the retry/backoff transport wrapper used by provider adapters.

All transports here are fakes — no test performs real network I/O.
"""

from __future__ import annotations

import pytest

from backend.app.market_data.errors import (
    ProviderDataError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from backend.app.market_data.transport import fetch_with_retry


class _FakeTransport:
    """Returns/raises from a scripted sequence, one entry per call."""

    def __init__(self, script: list[object]) -> None:
        self._script = list(script)
        self.calls: list[str] = []

    def fetch(self, url: str, *, timeout: float) -> str:
        self.calls.append(url)
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, str)
        return outcome


async def _no_sleep(_seconds: float) -> None:
    return None


async def test_fetch_with_retry_returns_first_success() -> None:
    transport = _FakeTransport(["ok"])
    result = await fetch_with_retry(transport, "http://example", timeout=1.0, sleep=_no_sleep)
    assert result == "ok"
    assert transport.calls == ["http://example"]


async def test_fetch_with_retry_retries_transient_failures() -> None:
    transport = _FakeTransport([ProviderTimeoutError("slow"), ProviderUnavailableError("down"), "ok"])
    result = await fetch_with_retry(
        transport, "http://example", timeout=1.0, max_attempts=3, sleep=_no_sleep
    )
    assert result == "ok"
    assert len(transport.calls) == 3


async def test_fetch_with_retry_retries_rate_limit() -> None:
    transport = _FakeTransport([ProviderRateLimitedError("429"), "ok"])
    result = await fetch_with_retry(
        transport, "http://example", timeout=1.0, max_attempts=2, sleep=_no_sleep
    )
    assert result == "ok"


async def test_fetch_with_retry_exhausts_attempts_and_raises_last_error() -> None:
    transport = _FakeTransport(
        [ProviderTimeoutError("1"), ProviderTimeoutError("2"), ProviderTimeoutError("3")]
    )
    with pytest.raises(ProviderTimeoutError):
        await fetch_with_retry(transport, "http://example", timeout=1.0, max_attempts=3, sleep=_no_sleep)
    assert len(transport.calls) == 3


async def test_fetch_with_retry_does_not_retry_data_errors() -> None:
    transport = _FakeTransport([ProviderDataError("bad payload"), "ok"])
    with pytest.raises(ProviderDataError):
        await fetch_with_retry(transport, "http://example", timeout=1.0, max_attempts=3, sleep=_no_sleep)
    assert len(transport.calls) == 1


async def test_fetch_with_retry_backoff_delays_are_exponential() -> None:
    transport = _FakeTransport([ProviderTimeoutError("1"), ProviderTimeoutError("2"), "ok"])
    delays: list[float] = []

    async def _record_sleep(seconds: float) -> None:
        delays.append(seconds)

    result = await fetch_with_retry(
        transport,
        "http://example",
        timeout=1.0,
        max_attempts=3,
        backoff_base_seconds=0.1,
        sleep=_record_sleep,
    )
    assert result == "ok"
    assert delays == [0.1, 0.2]


async def test_fetch_with_retry_rejects_non_positive_max_attempts() -> None:
    with pytest.raises(ValueError):
        await fetch_with_retry(
            _FakeTransport(["ok"]), "http://example", timeout=1.0, max_attempts=0, sleep=_no_sleep
        )
