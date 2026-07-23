"""``Indicator`` — common interface every technical indicator implements.

All computation is deterministic, local, and Decimal-based — no AI is
involved in indicator math (see the PROJECT_SPEC.md Section 5 scanner
requirement that deterministic calculations precede any AI involvement).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from backend.app.indicators.types import IndicatorResult
from shared.models.candle import Candle


class Indicator(ABC):
    """Abstract base for every deterministic technical indicator.

    Implementations must not silently propagate NaN/Infinity, must not use
    any future candle to compute a given point (no lookahead), and must
    raise ``InsufficientDataError`` rather than guess when given fewer
    candles than ``warmup_period`` requires.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short, stable identifier for this indicator (e.g. 'rsi_14')."""

    @property
    @abstractmethod
    def warmup_period(self) -> int:
        """Minimum number of candles needed before the first valid point."""

    @abstractmethod
    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        """Compute this indicator over an ordered, single-symbol/timeframe
        candle series. Callers normally go through ``IndicatorEngine``,
        which validates the series before calling this."""
