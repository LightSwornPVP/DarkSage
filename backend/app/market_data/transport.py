"""HTTP transport abstraction for market-data provider adapters.

Concrete providers depend on the ``Transport`` protocol, never on a specific
HTTP library, so:

- the rest of DarkSage stays provider-independent (ARCHITECTURE.md Section 7)
- tests substitute a deterministic fake and never need real network access
  or credentials (see tests/test_market_data_transport.py)

``UrllibTransport`` is the default, real implementation. It is built on the
standard library only, so exercising a real provider requires no new
dependency.
"""

from __future__ import annotations

import asyncio
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from typing import Protocol

from backend.app.market_data.errors import (
    ProviderDataError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

# Errors from a single attempt that are worth retrying: transient network or
# server-side conditions. A ProviderDataError (bad payload from a request
# that otherwise succeeded) is not retried — retrying it would just waste
# time reproducing the same bad response.
_RETRYABLE_ERRORS: tuple[type[ProviderError], ...] = (
    ProviderTimeoutError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)


class Transport(Protocol):
    """Fetches raw text from a URL. Implementations are synchronous —
    provider code runs them off the event loop via ``asyncio.to_thread``."""

    def fetch(self, url: str, *, timeout: float) -> str: ...


class UrllibTransport:
    """Default ``Transport``, built on ``urllib`` (standard library only)."""

    def fetch(self, url: str, *, timeout: float) -> str:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
                charset = response.headers.get_content_charset() or "utf-8"
                return str(response.read().decode(charset))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise ProviderRateLimitedError(f"{url} rate-limited (HTTP 429)") from exc
            if 500 <= exc.code < 600:
                raise ProviderUnavailableError(f"{url} returned HTTP {exc.code}") from exc
            raise ProviderDataError(f"{url} returned HTTP {exc.code}") from exc
        except TimeoutError as exc:
            raise ProviderTimeoutError(f"request to {url} timed out after {timeout}s") from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailableError(f"request to {url} failed: {exc.reason}") from exc


async def fetch_with_retry(
    transport: Transport,
    url: str,
    *,
    timeout: float,
    max_attempts: int = 3,
    backoff_base_seconds: float = 0.5,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> str:
    """Fetch ``url`` via ``transport``, retrying retryable failures with
    exponential backoff (``backoff_base_seconds * 2**attempt_index``).

    ``max_attempts`` is the total number of tries, including the first —
    ``max_attempts=1`` disables retrying. Non-retryable errors
    (``ProviderDataError``) propagate immediately on the first occurrence.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_error: ProviderError | None = None
    for attempt_index in range(max_attempts):
        try:
            return await asyncio.to_thread(transport.fetch, url, timeout=timeout)
        except _RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt_index < max_attempts - 1:
                await sleep(backoff_base_seconds * (2**attempt_index))

    assert last_error is not None  # noqa: S101 — loop always runs >= 1 time
    raise last_error
