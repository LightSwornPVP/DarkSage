"""Error taxonomy for the backtesting engine.

Every failure mode fails closed with a specific, catchable exception rather
than guessing or silently producing a degenerate result (NaN/Infinity,
empty-but-"successful" runs, etc.).
"""

from __future__ import annotations


class BacktestError(Exception):
    """Base class for all backtesting failures."""


class InvalidBacktestConfigError(BacktestError):
    """A ``BacktestConfig`` is internally inconsistent (e.g. end before
    start, negative capital, invalid cost assumptions)."""


class InvalidHistoryError(BacktestError):
    """The supplied candle history is not usable for a backtest: empty,
    mixed symbol/timeframe, non-increasing timestamps, or outside the
    configured date boundaries."""


class InsufficientHistoryError(BacktestError):
    """Fewer candles were supplied than a strategy's warm-up period, or the
    configured date range, requires."""


class InvalidExecutionConfigError(BacktestError):
    """A cost/execution configuration is ambiguous or invalid (e.g. a
    negative commission rate, an unrecognized fill-timing rule)."""


class InvalidPartitionError(BacktestError):
    """A date partition (train/validation/test, or a walk-forward window)
    is malformed, overlaps another partition, or cannot be constructed
    from the given bounds — e.g. windows that don't fit, or an
    out-of-sample period that overlaps its own in-sample period."""
