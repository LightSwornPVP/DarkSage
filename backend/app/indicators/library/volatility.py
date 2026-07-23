"""Volatility indicators: Bollinger Bands, Average True Range (ATR)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from backend.app.indicators.base import Indicator
from backend.app.indicators.errors import InsufficientDataError
from backend.app.indicators.types import IndicatorPoint, IndicatorResult
from shared.models.candle import Candle


class BollingerBandsIndicator(Indicator):
    """Bollinger Bands: middle SMA, upper/lower bands at ``num_std``
    population standard deviations."""

    def __init__(self, period: int = 20, num_std: int = 2) -> None:
        if period < 2:
            raise ValueError("period must be >= 2")
        if num_std <= 0:
            raise ValueError("num_std must be > 0")
        self._period = period
        self._num_std = num_std

    @property
    def name(self) -> str:
        return f"bollinger_{self._period}_{self._num_std}"

    @property
    def warmup_period(self) -> int:
        return self._period

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"{self.name} needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        period = self._period
        period_decimal = Decimal(period)
        num_std_decimal = Decimal(self._num_std)
        closes = [candle.close for candle in candles]

        points: list[IndicatorPoint] = []
        for index in range(period - 1, len(candles)):
            window = closes[index - period + 1 : index + 1]
            mean = sum(window, start=Decimal(0)) / period_decimal
            variance = sum(((value - mean) ** 2 for value in window), start=Decimal(0)) / period_decimal
            std_dev = variance.sqrt()
            points.append(
                IndicatorPoint(
                    timestamp=candles[index].timestamp,
                    values={
                        "middle": mean,
                        "upper": mean + num_std_decimal * std_dev,
                        "lower": mean - num_std_decimal * std_dev,
                    },
                )
            )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=tuple(points))


class ATRIndicator(Indicator):
    """Average True Range, using Wilder's smoothing."""

    def __init__(self, period: int = 14) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period

    @property
    def name(self) -> str:
        return f"atr_{self._period}"

    @property
    def warmup_period(self) -> int:
        return self._period + 1

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"{self.name} needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        period = self._period
        period_decimal = Decimal(period)

        true_ranges: list[Decimal] = []
        for index in range(1, len(candles)):
            high = candles[index].high
            low = candles[index].low
            previous_close = candles[index - 1].close
            true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))

        atr = sum(true_ranges[:period], start=Decimal(0)) / period_decimal
        atr_values = [atr]
        for index in range(period, len(true_ranges)):
            atr = (atr * (period_decimal - 1) + true_ranges[index]) / period_decimal
            atr_values.append(atr)

        points = tuple(
            IndicatorPoint(timestamp=candle.timestamp, values={"atr": value})
            for candle, value in zip(candles[period:], atr_values, strict=True)
        )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=points)
