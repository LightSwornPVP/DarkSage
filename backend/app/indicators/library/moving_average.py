"""Moving-average indicators: simple (SMA) and exponential (EMA).

Both are parameterized by period rather than hard-coded per period, so the
Phase 1 default set (EMA 9/20/50/100/200, SMA 50/100/200) is just several
registered instances of the same two classes — see ``library/__init__.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.indicators.base import Indicator
from backend.app.indicators.errors import InsufficientDataError
from backend.app.indicators.rolling import ema_series, rolling_mean
from backend.app.indicators.types import IndicatorPoint, IndicatorResult
from shared.models.candle import Candle


class SMAIndicator(Indicator):
    """Simple moving average of close price over ``period`` candles."""

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period

    @property
    def name(self) -> str:
        return f"sma_{self._period}"

    @property
    def warmup_period(self) -> int:
        return self._period

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"{self.name} needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        closes = [candle.close for candle in candles]
        values = rolling_mean(closes, self._period)
        points = tuple(
            IndicatorPoint(timestamp=candle.timestamp, values={"sma": value})
            for candle, value in zip(candles[self._period - 1 :], values, strict=True)
        )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=points)


class EMAIndicator(Indicator):
    """Exponential moving average of close price over ``period`` candles."""

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period

    @property
    def name(self) -> str:
        return f"ema_{self._period}"

    @property
    def warmup_period(self) -> int:
        return self._period

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"{self.name} needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        closes = [candle.close for candle in candles]
        values = ema_series(closes, self._period)
        points = tuple(
            IndicatorPoint(timestamp=candle.timestamp, values={"ema": value})
            for candle, value in zip(candles[self._period - 1 :], values, strict=True)
        )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=points)
