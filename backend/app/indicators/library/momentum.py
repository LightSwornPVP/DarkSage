"""Momentum indicators: RSI, MACD, Williams %R.

ADX/DMI is intentionally not included in this slice — correctly
implementing Wilder's smoothed +DI/-DI/ADX chain has enough subtlety (and no
independently-verifiable reference data available in this offline slice)
that shipping it without confidence in its correctness would be worse than
deferring it. Tracked as backlog, not silently dropped.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from backend.app.indicators.base import Indicator
from backend.app.indicators.errors import InsufficientDataError
from backend.app.indicators.rolling import ema_series
from backend.app.indicators.types import IndicatorPoint, IndicatorResult
from shared.models.candle import Candle

_HUNDRED = Decimal(100)


def _rsi_from_averages(avg_gain: Decimal, avg_loss: Decimal) -> Decimal:
    if avg_loss == 0:
        # No losses in the window (including the all-flat case) — maximum
        # strength reading, not a division by zero.
        return _HUNDRED
    relative_strength = avg_gain / avg_loss
    return _HUNDRED - (_HUNDRED / (Decimal(1) + relative_strength))


class RSIIndicator(Indicator):
    """Wilder's Relative Strength Index."""

    def __init__(self, period: int = 14) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period

    @property
    def name(self) -> str:
        return f"rsi_{self._period}"

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
        closes = [candle.close for candle in candles]

        gains: list[Decimal] = []
        losses: list[Decimal] = []
        for index in range(1, len(closes)):
            change = closes[index] - closes[index - 1]
            gains.append(change if change > 0 else Decimal(0))
            losses.append(-change if change < 0 else Decimal(0))

        avg_gain = sum(gains[:period], start=Decimal(0)) / period_decimal
        avg_loss = sum(losses[:period], start=Decimal(0)) / period_decimal
        rsi_values = [_rsi_from_averages(avg_gain, avg_loss)]

        for index in range(period, len(gains)):
            avg_gain = (avg_gain * (period_decimal - 1) + gains[index]) / period_decimal
            avg_loss = (avg_loss * (period_decimal - 1) + losses[index]) / period_decimal
            rsi_values.append(_rsi_from_averages(avg_gain, avg_loss))

        points = tuple(
            IndicatorPoint(timestamp=candle.timestamp, values={"rsi": value})
            for candle, value in zip(candles[period:], rsi_values, strict=True)
        )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=points)


class MACDIndicator(Indicator):
    """Moving Average Convergence/Divergence: line, signal, and histogram."""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        if fast < 1 or slow < 1 or signal < 1:
            raise ValueError("fast, slow, and signal periods must be >= 1")
        if fast >= slow:
            raise ValueError("fast period must be < slow period")
        self._fast = fast
        self._slow = slow
        self._signal = signal

    @property
    def name(self) -> str:
        return f"macd_{self._fast}_{self._slow}_{self._signal}"

    @property
    def warmup_period(self) -> int:
        return self._slow + self._signal - 1

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"{self.name} needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        closes = [candle.close for candle in candles]

        fast_series = ema_series(closes, self._fast)  # starts at absolute index fast-1
        slow_series = ema_series(closes, self._slow)  # starts at absolute index slow-1

        # Align the fast series to the slow series' start (both are absolute
        # indices into `closes`), so both operands of the subtraction below
        # refer to the same candle.
        offset = self._slow - self._fast
        aligned_fast = fast_series[offset:]
        macd_line = [fast - slow for fast, slow in zip(aligned_fast, slow_series, strict=True)]

        signal_line = ema_series(macd_line, self._signal)
        aligned_macd = macd_line[self._signal - 1 :]
        histogram = [macd - signal for macd, signal in zip(aligned_macd, signal_line, strict=True)]

        start_index = self._slow + self._signal - 2
        points = tuple(
            IndicatorPoint(
                timestamp=candle.timestamp,
                values={"macd": macd_value, "signal": signal_value, "histogram": histogram_value},
            )
            for candle, macd_value, signal_value, histogram_value in zip(
                candles[start_index:], aligned_macd, signal_line, histogram, strict=True
            )
        )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=points)


class WilliamsPercentRIndicator(Indicator):
    """Williams %R: how close the close is to the period's high/low range."""

    def __init__(self, period: int = 14) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period

    @property
    def name(self) -> str:
        return f"williams_r_{self._period}"

    @property
    def warmup_period(self) -> int:
        return self._period

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"{self.name} needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        period = self._period
        points: list[IndicatorPoint] = []
        for index in range(period - 1, len(candles)):
            window = candles[index - period + 1 : index + 1]
            highest_high = max(candle.high for candle in window)
            lowest_low = min(candle.low for candle in window)
            denominator = highest_high - lowest_low
            if denominator == 0:
                # Flat range over the window: %R is mathematically undefined
                # here. Omit the point rather than fabricate a value or
                # divide by zero — never emit NaN/Infinity.
                continue
            value = (highest_high - candles[index].close) / denominator * Decimal(-100)
            points.append(IndicatorPoint(timestamp=candles[index].timestamp, values={"williams_r": value}))
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=tuple(points))
