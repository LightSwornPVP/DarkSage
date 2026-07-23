"""Tests for StooqProvider using a fake Transport (no real network, no
credentials) with canned CSV fixtures matching stooq.com's documented format.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.app.market_data.errors import ProviderDataError, ProviderUnsupportedOperationError
from backend.app.market_data.last_price import LastPrice, ensure_freshness_eligible
from backend.app.market_data.providers.stooq import StooqProvider
from shared.models.candle import Timeframe
from shared.models.quote import Quote

QUOTE_CSV = (
    "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
    "aapl.us,2026-01-01,21:59:59,190.0000,192.0000,189.0000,191.0000,50000000\n"
)

QUOTE_CSV_NO_DATA = "Symbol,Date,Time,Open,High,Low,Close,Volume\nnope.us,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n"

HISTORY_CSV = (
    "Date,Open,High,Low,Close,Volume\n"
    "2025-12-30,188.00,189.50,187.00,189.00,40000000\n"
    "2025-12-31,189.00,191.00,188.50,190.50,42000000\n"
    "2026-01-01,190.50,192.00,189.00,191.00,50000000\n"
)

HISTORY_CSV_NO_DATA = "No data"


class _FakeTransport:
    def __init__(
        self,
        *,
        quote_csv: str | None = None,
        history_csv: str | None = None,
    ) -> None:
        self._quote_csv = quote_csv
        self._history_csv = history_csv
        self.urls: list[str] = []

    def fetch(self, url: str, *, timeout: float) -> str:
        self.urls.append(url)
        if "/q/l/" in url:
            assert self._quote_csv is not None
            return self._quote_csv
        if "/q/d/l/" in url:
            assert self._history_csv is not None
            return self._history_csv
        raise AssertionError(f"unexpected URL: {url}")


async def _no_sleep(_seconds: float) -> None:
    return None


def _make_provider(**kwargs: object) -> StooqProvider:
    kwargs.setdefault("sleep", _no_sleep)
    return StooqProvider(**kwargs)  # type: ignore[arg-type]


def test_provider_name() -> None:
    assert _make_provider(transport=_FakeTransport()).name == "stooq"


# --- get_quote: Stooq has no real bid/ask, so it must not exist as a Quote
# (blocker 2) — the provider must fail closed instead of fabricating a spread.


async def test_get_quote_is_not_supported_and_never_fabricates_a_spread() -> None:
    provider = _make_provider(transport=_FakeTransport(quote_csv=QUOTE_CSV))
    with pytest.raises(ProviderUnsupportedOperationError):
        await provider.get_quote("aapl")


def test_stooq_provider_has_no_way_to_produce_a_quote_object() -> None:
    # Structural check, not just behavioral: nothing in this module builds a
    # Quote from Stooq data at all (no normalize_quote/RawQuote usage left).
    import inspect

    import backend.app.market_data.providers.stooq as stooq_module

    source = inspect.getsource(stooq_module)
    assert "normalize_quote" not in source
    assert "RawQuote" not in source


# --- get_last_price: the honest, structurally distinct replacement ---


async def test_get_last_price_parses_and_normalizes() -> None:
    transport = _FakeTransport(quote_csv=QUOTE_CSV)
    provider = _make_provider(transport=transport)

    last_price = await provider.get_last_price("aapl")

    assert isinstance(last_price, LastPrice)
    assert not isinstance(last_price, Quote)  # structurally distinct — never masquerades as a real Quote
    assert last_price.symbol == "AAPL"  # canonical symbol, not the vendor-suffixed one
    assert str(last_price.price) == "191.0000"
    assert last_price.timestamp == datetime(2026, 1, 1, 21, 59, 59, tzinfo=timezone.utc)
    assert last_price.timestamp_basis == "unverified"  # Stooq's timezone is not documented
    assert "aapl.us" in transport.urls[0]


async def test_get_last_price_raises_provider_data_error_on_no_data() -> None:
    provider = _make_provider(transport=_FakeTransport(quote_csv=QUOTE_CSV_NO_DATA))
    with pytest.raises(ProviderDataError):
        await provider.get_last_price("nope")


async def test_get_last_price_timestamp_basis_fails_freshness_eligibility() -> None:
    provider = _make_provider(transport=_FakeTransport(quote_csv=QUOTE_CSV))
    last_price = await provider.get_last_price("aapl")
    # Unsafe/unknown timestamp semantics must never pass a freshness check —
    # there is no bypass for "unverified" data, by design.
    with pytest.raises(ProviderDataError):
        ensure_freshness_eligible(last_price)


def test_ensure_freshness_eligible_accepts_verified_basis() -> None:
    verified = LastPrice(
        symbol="AAPL",
        price=Decimal("100"),
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        timestamp_basis="verified",
    )
    ensure_freshness_eligible(verified)  # must not raise


async def test_get_historical_candles_filters_by_range() -> None:
    provider = _make_provider(transport=_FakeTransport(history_csv=HISTORY_CSV))
    candles = await provider.get_historical_candles(
        "aapl",
        Timeframe.D1,
        start=datetime(2025, 12, 31, tzinfo=timezone.utc),
        end=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert [c.timestamp.date().isoformat() for c in candles] == ["2025-12-31", "2026-01-01"]
    assert all(c.symbol == "AAPL" for c in candles)


async def test_get_historical_candles_rejects_non_daily_timeframe() -> None:
    provider = _make_provider(transport=_FakeTransport(history_csv=HISTORY_CSV))
    with pytest.raises(ProviderDataError):
        await provider.get_historical_candles(
            "aapl",
            Timeframe.M1,
            start=datetime(2025, 12, 31, tzinfo=timezone.utc),
            end=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


async def test_get_historical_candles_rejects_naive_datetimes() -> None:
    provider = _make_provider(transport=_FakeTransport(history_csv=HISTORY_CSV))
    with pytest.raises(ValueError):
        await provider.get_historical_candles(
            "aapl", Timeframe.D1, start=datetime(2025, 12, 31), end=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )


async def test_get_historical_candles_raises_on_no_data() -> None:
    provider = _make_provider(transport=_FakeTransport(history_csv=HISTORY_CSV_NO_DATA))
    with pytest.raises(ProviderDataError):
        await provider.get_historical_candles(
            "nope",
            Timeframe.D1,
            start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


async def test_get_candles_returns_most_recent_limit() -> None:
    provider = _make_provider(transport=_FakeTransport(history_csv=HISTORY_CSV))
    candles = await provider.get_candles("aapl", Timeframe.D1, limit=2)
    assert [c.timestamp.date().isoformat() for c in candles] == ["2025-12-31", "2026-01-01"]


async def test_get_candles_rejects_non_positive_limit() -> None:
    provider = _make_provider(transport=_FakeTransport(history_csv=HISTORY_CSV))
    with pytest.raises(ValueError):
        await provider.get_candles("aapl", Timeframe.D1, limit=0)


@pytest.mark.parametrize("method_name", ["get_company_info", "get_fundamentals", "get_news"])
async def test_unsupported_operations_raise_clearly(method_name: str) -> None:
    provider = _make_provider(transport=_FakeTransport())
    method = getattr(provider, method_name)
    with pytest.raises(ProviderUnsupportedOperationError):
        await method("aapl")


async def test_get_market_status_raises_unsupported() -> None:
    provider = _make_provider(transport=_FakeTransport())
    with pytest.raises(ProviderUnsupportedOperationError):
        await provider.get_market_status()
