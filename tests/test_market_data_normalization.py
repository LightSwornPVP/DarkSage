"""Tests for the provider-independent market-data normalization layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.market_data.normalization import (
    NormalizationError,
    RawCandle,
    RawQuote,
    normalize_candle,
    normalize_quote,
)
from shared.models.candle import Timeframe

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
NON_UTC_AWARE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=-5)))


def _raw_candle(**overrides: object) -> RawCandle:
    fields: dict[str, object] = dict(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=NOW,
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("99"),
        close=Decimal("104"),
        volume=Decimal("1000"),
    )
    fields.update(overrides)
    return RawCandle(**fields)  # type: ignore[arg-type]


def _raw_quote(**overrides: object) -> RawQuote:
    fields: dict[str, object] = dict(
        symbol="AAPL",
        timestamp=NOW,
        bid=Decimal("100"),
        ask=Decimal("100.5"),
        last=Decimal("100.2"),
        volume=Decimal("500"),
    )
    fields.update(overrides)
    return RawQuote(**fields)  # type: ignore[arg-type]


# --- Valid candle / quote ---


def test_normalize_candle_valid() -> None:
    candle = normalize_candle(_raw_candle())
    assert candle.symbol == "AAPL"
    assert candle.open == Decimal("100")
    assert candle.timestamp == NOW


def test_normalize_quote_valid() -> None:
    quote = normalize_quote(_raw_quote())
    assert quote.symbol == "AAPL"
    assert quote.bid == Decimal("100")
    assert quote.timestamp == NOW


# --- Symbol normalization ---


def test_normalize_candle_symbol_stripped_and_uppercased() -> None:
    candle = normalize_candle(_raw_candle(symbol="  aapl  "))
    assert candle.symbol == "AAPL"


def test_normalize_quote_symbol_stripped_and_uppercased() -> None:
    quote = normalize_quote(_raw_quote(symbol="  aapl  "))
    assert quote.symbol == "AAPL"


def test_normalize_candle_rejects_blank_symbol() -> None:
    with pytest.raises(NormalizationError):
        normalize_candle(_raw_candle(symbol="   "))


def test_normalize_quote_rejects_blank_symbol() -> None:
    with pytest.raises(NormalizationError):
        normalize_quote(_raw_quote(symbol=""))


# --- Decimal preservation ---


def test_normalize_candle_preserves_decimal_precision() -> None:
    candle = normalize_candle(_raw_candle(close=Decimal("104.123456789")))
    assert candle.close == Decimal("104.123456789")


# --- Numeric conversion: int / string / float ---


def test_normalize_candle_accepts_int_numeric_input() -> None:
    candle = normalize_candle(_raw_candle(open=100, high=105, low=99, close=104, volume=1000))
    assert candle.open == Decimal(100)
    assert isinstance(candle.open, Decimal)


def test_normalize_candle_accepts_numeric_string_input() -> None:
    candle = normalize_candle(_raw_candle(close="104.75"))
    assert candle.close == Decimal("104.75")


def test_normalize_candle_accepts_float_input_via_str_conversion() -> None:
    candle = normalize_candle(_raw_candle(close=104.75))
    assert candle.close == Decimal("104.75")


def test_normalize_quote_accepts_mixed_numeric_types() -> None:
    quote = normalize_quote(_raw_quote(bid=100, ask="100.5", last=100.2))
    assert quote.bid == Decimal(100)
    assert quote.ask == Decimal("100.5")
    assert quote.last == Decimal("100.2")


# --- NaN / Infinity rejection across representations ---


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_normalize_candle_rejects_non_finite_float(bad_value: float) -> None:
    with pytest.raises(NormalizationError):
        normalize_candle(_raw_candle(close=bad_value))


@pytest.mark.parametrize("bad_value", [Decimal("nan"), Decimal("inf"), Decimal("-inf")])
def test_normalize_candle_rejects_non_finite_decimal(bad_value: Decimal) -> None:
    with pytest.raises(NormalizationError):
        normalize_candle(_raw_candle(close=bad_value))


@pytest.mark.parametrize("bad_value", ["nan", "Infinity", "-Infinity"])
def test_normalize_candle_rejects_non_finite_string(bad_value: str) -> None:
    with pytest.raises(NormalizationError):
        normalize_candle(_raw_candle(close=bad_value))


@pytest.mark.parametrize("bad_value", [float("nan"), Decimal("inf"), "-infinity"])
def test_normalize_quote_rejects_non_finite_values(bad_value: object) -> None:
    with pytest.raises(NormalizationError):
        normalize_quote(_raw_quote(last=bad_value))


# --- Timestamp handling ---


def test_normalize_candle_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        normalize_candle(_raw_candle(timestamp=datetime(2026, 1, 1)))


def test_normalize_quote_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        normalize_quote(_raw_quote(timestamp=datetime(2026, 1, 1)))


def test_normalize_candle_normalizes_aware_timestamp_to_utc() -> None:
    candle = normalize_candle(_raw_candle(timestamp=NON_UTC_AWARE))
    assert candle.timestamp.tzinfo == timezone.utc
    assert candle.timestamp == NON_UTC_AWARE.astimezone(timezone.utc)


def test_normalize_quote_normalizes_aware_timestamp_to_utc() -> None:
    quote = normalize_quote(_raw_quote(timestamp=NON_UTC_AWARE))
    assert quote.timestamp.tzinfo == timezone.utc
    assert quote.timestamp == NON_UTC_AWARE.astimezone(timezone.utc)


# --- Quote-specific rules ---


def test_normalize_quote_rejects_ask_below_bid() -> None:
    with pytest.raises(ValidationError):
        normalize_quote(_raw_quote(bid=Decimal("101"), ask=Decimal("100")))


def test_normalize_quote_volume_is_optional() -> None:
    quote = normalize_quote(_raw_quote(volume=None))
    assert quote.volume is None


# --- Missing mandatory Candle fields ---


def test_normalize_candle_missing_volume_raises() -> None:
    with pytest.raises(TypeError):
        RawCandle(  # type: ignore[call-arg]
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=NOW,
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("104"),
        )


# --- Invalid zero/negative prices (enforced by the domain model) ---


def test_normalize_candle_rejects_zero_price() -> None:
    with pytest.raises(ValidationError):
        normalize_candle(_raw_candle(open=0))


def test_normalize_candle_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        normalize_candle(_raw_candle(open=-5))


def test_normalize_quote_rejects_zero_price() -> None:
    with pytest.raises(ValidationError):
        normalize_quote(_raw_quote(bid=0))
