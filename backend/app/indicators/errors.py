"""Error taxonomy for the indicator engine.

Indicators fail closed: insufficient history or an invalid candle series
raises one of these rather than returning a partial, zero, or NaN result.
"""

from __future__ import annotations


class IndicatorError(Exception):
    """Base class for all indicator-engine failures."""


class InsufficientDataError(IndicatorError):
    """Fewer candles were supplied than the indicator's warm-up period requires."""


class InvalidCandleSeriesError(IndicatorError):
    """The supplied candle series is not a single, ordered, gap-free-by-symbol
    series an indicator can safely compute over (e.g. mixed symbols, mixed
    timeframes, or non-increasing timestamps)."""
