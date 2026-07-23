"""StooqProvider — a real ``MarketDataProvider`` backed by stooq.com's free,
no-API-key CSV endpoints.

Chosen for Phase 1 specifically because it requires no account, no API key,
and no paid plan (SECURITY_RULES.md, TRADING_RULES.md: no paid services /
credentials in this slice), so it can be exercised safely in an open-source
tree. Nothing outside this module may assume Stooq specifically is in use —
callers depend only on ``MarketDataProvider`` (ARCHITECTURE.md Section 7).

Known limitations of this slice (tracked as backlog, not blockers):

- Only daily (``Timeframe.D1``) candles are supported; Stooq's free tier
  does not reliably offer intraday history.
- Stooq's free quote endpoint has no real bid/ask — ``bid``/``ask``/``last``
  are all set to the same last-trade price, so ``Quote.spread`` is always 0.
- Quote timestamps are treated as UTC. Stooq does not document its
  timestamp timezone; this should be verified against live traffic before
  the freshness/staleness check is relied on for time-sensitive decisions.
- Symbol mapping assumes a plain US-listed equity (``symbol.lower() + ".us"``);
  it does not yet handle other exchanges or class-share suffix conventions.
"""

from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from urllib.parse import quote as url_quote

from backend.app.market_data.errors import (
    ProviderDataError,
    ProviderUnsupportedOperationError,
    StaleDataError,
)
from backend.app.market_data.freshness import is_stale
from backend.app.market_data.normalization import RawCandle, RawQuote, normalize_candle, normalize_quote
from backend.app.market_data.provider import MarketDataProvider
from backend.app.market_data.rate_limit import RateLimiter
from backend.app.market_data.transport import Transport, UrllibTransport, fetch_with_retry
from shared.models.candle import Candle, Timeframe
from shared.models.quote import Quote

_NO_DATA_MARKERS = frozenset({"N/D", ""})

_QUOTE_FIELDS = ("Date", "Time", "Open", "High", "Low", "Close")
_HISTORY_FIELDS = ("Date", "Open", "High", "Low", "Close", "Volume")


def _to_vendor_symbol(symbol: str) -> str:
    """Map a canonical DarkSage symbol to a Stooq query symbol.

    This vendor-specific translation lives here, not in ``shared/models`` —
    the domain models must never know a symbol suffix convention exists.
    """
    return url_quote(f"{symbol.strip().lower()}.us", safe=".")


def _parse_stooq_quote_csv(raw_text: str, *, symbol: str) -> RawQuote:
    reader = csv.DictReader(io.StringIO(raw_text.strip()))
    try:
        row = next(reader)
    except StopIteration as exc:
        raise ProviderDataError(f"{symbol}: stooq quote response had no data rows") from exc

    missing = [field for field in _QUOTE_FIELDS if field not in row]
    if missing:
        raise ProviderDataError(f"{symbol}: stooq quote response missing field(s) {missing}")

    if any(row[field].strip() in _NO_DATA_MARKERS for field in ("Open", "High", "Low", "Close")):
        raise ProviderDataError(f"{symbol}: stooq has no quote data for this symbol")

    try:
        naive_timestamp = datetime.strptime(f"{row['Date']} {row['Time']}", "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ProviderDataError(
            f"{symbol}: unparseable stooq quote timestamp {row['Date']!r} {row['Time']!r}"
        ) from exc
    timestamp = naive_timestamp.replace(tzinfo=timezone.utc)

    volume_raw = row.get("Volume", "").strip()
    volume = volume_raw if volume_raw and volume_raw not in _NO_DATA_MARKERS else None

    # Stooq's free snapshot has no real bid/ask — last trade price stands in
    # for both, so Quote.spread is always 0 for this provider (see module
    # docstring). This is an honest limitation, not a fabricated spread.
    return RawQuote(
        symbol=symbol,
        timestamp=timestamp,
        bid=row["Close"],
        ask=row["Close"],
        last=row["Close"],
        volume=volume,
    )


def _parse_stooq_history_csv(raw_text: str, *, symbol: str, timeframe: Timeframe) -> list[RawCandle]:
    stripped = raw_text.strip()
    if not stripped or stripped.lower().startswith("no data"):
        return []

    reader = csv.DictReader(io.StringIO(stripped))
    raw_candles: list[RawCandle] = []
    for row in reader:
        missing = [field for field in _HISTORY_FIELDS if field not in row]
        if missing:
            raise ProviderDataError(f"{symbol}: stooq history response missing field(s) {missing}")

        if any(row[field].strip() in _NO_DATA_MARKERS for field in _HISTORY_FIELDS):
            continue  # a row stooq marked as having no data for that date

        try:
            date_value = datetime.strptime(row["Date"], "%Y-%m-%d")
        except ValueError as exc:
            raise ProviderDataError(f"{symbol}: unparseable stooq history date {row['Date']!r}") from exc
        timestamp = date_value.replace(tzinfo=timezone.utc)

        raw_candles.append(
            RawCandle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=row["Volume"],
            )
        )
    return raw_candles


class StooqProvider(MarketDataProvider):
    """``MarketDataProvider`` backed by stooq.com's free CSV endpoints."""

    _QUOTE_URL_TEMPLATE = "https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
    _HISTORY_URL_TEMPLATE = "https://stooq.com/q/d/l/?s={symbol}&i=d"

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        rate_limiter: RateLimiter | None = None,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        backoff_base_seconds: float = 0.5,
        max_quote_age: timedelta | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._transport = transport if transport is not None else UrllibTransport()
        self._rate_limiter = rate_limiter
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._backoff_base_seconds = backoff_base_seconds
        self._max_quote_age = max_quote_age
        self._sleep = sleep
        self._clock = clock

    @property
    def name(self) -> str:
        return "stooq"

    async def _get(self, url: str) -> str:
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()
        return await fetch_with_retry(
            self._transport,
            url,
            timeout=self._timeout_seconds,
            max_attempts=self._max_attempts,
            backoff_base_seconds=self._backoff_base_seconds,
            sleep=self._sleep,
        )

    async def get_quote(self, symbol: str) -> Quote:
        url = self._QUOTE_URL_TEMPLATE.format(symbol=_to_vendor_symbol(symbol))
        raw_text = await self._get(url)
        raw_quote = _parse_stooq_quote_csv(raw_text, symbol=symbol)
        quote = normalize_quote(raw_quote)

        if self._max_quote_age is not None:
            now = self._clock()
            if is_stale(quote.timestamp, max_age=self._max_quote_age, now=now):
                raise StaleDataError(
                    f"{symbol}: quote timestamp {quote.timestamp.isoformat()} exceeds "
                    f"configured max age {self._max_quote_age}"
                )
        return quote

    async def _fetch_daily_candles(self, symbol: str, timeframe: Timeframe) -> list[Candle]:
        if timeframe is not Timeframe.D1:
            raise ProviderDataError(
                f"StooqProvider supports only {Timeframe.D1.value} candles in this slice "
                f"(requested {timeframe.value})"
            )
        url = self._HISTORY_URL_TEMPLATE.format(symbol=_to_vendor_symbol(symbol))
        raw_text = await self._get(url)
        raw_candles = _parse_stooq_history_csv(raw_text, symbol=symbol, timeframe=timeframe)
        if not raw_candles:
            raise ProviderDataError(f"{symbol}: no historical candle data returned by stooq")
        return [normalize_candle(raw_candle) for raw_candle in raw_candles]

    async def get_candles(self, symbol: str, timeframe: Timeframe, *, limit: int = 100) -> list[Candle]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        candles = await self._fetch_daily_candles(symbol, timeframe)
        return candles[-limit:]

    async def get_historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if end < start:
            raise ValueError("end must be >= start")
        candles = await self._fetch_daily_candles(symbol, timeframe)
        return [candle for candle in candles if start <= candle.timestamp <= end]

    async def get_company_info(self, symbol: str) -> dict[str, str]:
        raise ProviderUnsupportedOperationError(
            "StooqProvider does not implement get_company_info in this slice"
        )

    async def get_fundamentals(self, symbol: str) -> dict[str, float]:
        raise ProviderUnsupportedOperationError(
            "StooqProvider does not implement get_fundamentals in this slice"
        )

    async def get_news(self, symbol: str, *, limit: int = 10) -> list[dict[str, str]]:
        raise ProviderUnsupportedOperationError(
            "StooqProvider does not implement get_news in this slice"
        )

    async def get_market_status(self) -> str:
        raise ProviderUnsupportedOperationError(
            "StooqProvider does not implement get_market_status in this slice"
        )
