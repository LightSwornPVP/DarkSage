"""Normalizer — converts raw, provider-specific market-data values into the
strict, provider-agnostic ``Candle`` and ``Quote`` domain models.

See ARCHITECTURE.md Section 7 (Market Data Architecture):

    Provider -> Adapter -> Normalizer -> Cache / Database -> Scanner / Charts / ...

This module is the "Normalizer" stage. It does not talk to any provider; it
only knows how to turn already-fetched raw values into domain models. Final
field-level validation (price positivity, OHLC consistency, bid/ask spread,
UTC conversion) is left to ``Candle``/``Quote`` themselves so those rules are
defined in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from shared.models.candle import Candle, Timeframe
from shared.models.quote import Quote

# Raw numeric input as it may arrive from a provider's payload, before it has
# been coerced into a precision-safe Decimal.
RawNumeric = Decimal | int | float | str


class NormalizationError(ValueError):
    """Raised when raw market-data input cannot be normalized."""


@dataclass(frozen=True, slots=True)
class RawCandle:
    """Raw OHLCV values for one candle, as received from a provider adapter."""

    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    open: RawNumeric
    high: RawNumeric
    low: RawNumeric
    close: RawNumeric
    volume: RawNumeric


@dataclass(frozen=True, slots=True)
class RawQuote:
    """Raw bid/ask/last values for one quote, as received from a provider adapter."""

    symbol: str
    timestamp: datetime
    bid: RawNumeric
    ask: RawNumeric
    last: RawNumeric
    volume: RawNumeric | None = None


def _normalize_symbol(symbol: str) -> str:
    stripped = symbol.strip()
    if not stripped:
        raise NormalizationError("symbol is empty after trimming whitespace")
    return stripped.upper()


def _to_decimal(value: RawNumeric, *, field: str) -> Decimal:
    """Convert a raw numeric value to Decimal without ever routing a float
    through ``Decimal(float)``, which would bake in binary floating-point
    representation error."""
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, bool):
        raise NormalizationError(f"{field}: boolean is not a valid numeric input")
    elif isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, float):
        decimal_value = Decimal(str(value))
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise NormalizationError(f"{field}: empty numeric string")
        try:
            decimal_value = Decimal(stripped)
        except InvalidOperation as exc:
            raise NormalizationError(f"{field}: {value!r} is not a valid number") from exc
    else:
        raise NormalizationError(f"{field}: unsupported numeric input type {type(value)!r}")

    if decimal_value.is_nan() or decimal_value.is_infinite():
        raise NormalizationError(f"{field}: NaN and Infinity are not allowed")

    return decimal_value


def normalize_candle(raw: RawCandle) -> Candle:
    """Normalize a ``RawCandle`` into a validated domain ``Candle``.

    Domain-level rules (OHLC consistency, positivity, timezone-aware
    timestamp normalization to UTC) are enforced by ``Candle`` itself.
    """
    return Candle(
        symbol=_normalize_symbol(raw.symbol),
        timeframe=raw.timeframe,
        timestamp=raw.timestamp,
        open=_to_decimal(raw.open, field="open"),
        high=_to_decimal(raw.high, field="high"),
        low=_to_decimal(raw.low, field="low"),
        close=_to_decimal(raw.close, field="close"),
        volume=_to_decimal(raw.volume, field="volume"),
    )


def normalize_quote(raw: RawQuote) -> Quote:
    """Normalize a ``RawQuote`` into a validated domain ``Quote``.

    Domain-level rules (bid/ask spread, positivity, timezone-aware timestamp
    normalization to UTC) are enforced by ``Quote`` itself.
    """
    return Quote(
        symbol=_normalize_symbol(raw.symbol),
        timestamp=raw.timestamp,
        bid=_to_decimal(raw.bid, field="bid"),
        ask=_to_decimal(raw.ask, field="ask"),
        last=_to_decimal(raw.last, field="last"),
        volume=_to_decimal(raw.volume, field="volume") if raw.volume is not None else None,
    )
