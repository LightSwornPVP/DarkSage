"""Typed result structures produced by the indicator engine.

An indicator may be single-valued (e.g. RSI) or multi-valued (e.g. MACD's
line/signal/histogram, or Bollinger's upper/middle/lower band) — ``values``
is a mapping so both shapes use the same result type.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from shared.models.candle import Timeframe


@dataclass(frozen=True, slots=True)
class IndicatorPoint:
    """One indicator value (or set of named values) at one candle's timestamp."""

    timestamp: datetime
    values: Mapping[str, Decimal]


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    """The full output of computing one indicator over a candle series.

    ``points`` never contains a warm-up placeholder — it only holds
    timestamps for which the indicator produced a real, finite value. If the
    input had fewer candles than the indicator's warm-up period requires,
    computing the indicator raises ``InsufficientDataError`` instead of
    returning an empty or partial result.
    """

    name: str
    timeframe: Timeframe
    points: tuple[IndicatorPoint, ...]

    @property
    def latest(self) -> IndicatorPoint | None:
        return self.points[-1] if self.points else None
