"""Volume indicators: raw volume, average volume, relative volume (RVOL),
On-Balance Volume (OBV), and Chaikin Money Flow (CMF).

MFI was considered and skipped in favor of CMF: CMF's money-flow-multiplier
formula is simple and unambiguous, while MFI additionally requires an
RSI-style smoothed positive/negative money-flow ratio, which is more
surface area than this slice needs for one well-scoped volume/participation
signal (instructions: "MFI or CMF only if implementation remains
well-scoped").
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from backend.app.indicators.base import Indicator
from backend.app.indicators.errors import InsufficientDataError
from backend.app.indicators.rolling import rolling_mean
from backend.app.indicators.types import IndicatorPoint, IndicatorResult
from shared.models.candle import Candle


class VolumeIndicator(Indicator):
    """Raw candle volume, exposed through the same Indicator interface as
    every derived volume signal."""

    @property
    def name(self) -> str:
        return "volume"

    @property
    def warmup_period(self) -> int:
        return 1

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(f"{self.name} needs at least 1 candle, got {len(candles)}")
        points = tuple(
            IndicatorPoint(timestamp=candle.timestamp, values={"volume": candle.volume})
            for candle in candles
        )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=points)


class AverageVolumeIndicator(Indicator):
    """Simple moving average of volume over ``period`` candles."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period

    @property
    def name(self) -> str:
        return f"avg_volume_{self._period}"

    @property
    def warmup_period(self) -> int:
        return self._period

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"{self.name} needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        volumes = [candle.volume for candle in candles]
        values = rolling_mean(volumes, self._period)
        points = tuple(
            IndicatorPoint(timestamp=candle.timestamp, values={"avg_volume": value})
            for candle, value in zip(candles[self._period - 1 :], values, strict=True)
        )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=points)


class RelativeVolumeIndicator(Indicator):
    """RVOL[i] = volume[i] / average(volume[i-period:i]) — today's volume
    compared to a trailing baseline that excludes today, so a spike is
    measured against an average it hasn't itself distorted."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period

    @property
    def name(self) -> str:
        return f"rvol_{self._period}"

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
        points: list[IndicatorPoint] = []
        for index in range(period, len(candles)):
            window = candles[index - period : index]
            avg_volume = sum((candle.volume for candle in window), start=Decimal(0)) / period_decimal
            if avg_volume == 0:
                # No baseline volume to compare against — omit rather than
                # divide by zero.
                continue
            rvol = candles[index].volume / avg_volume
            points.append(IndicatorPoint(timestamp=candles[index].timestamp, values={"rvol": rvol}))
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=tuple(points))


class OBVIndicator(Indicator):
    """On-Balance Volume: a running total that adds volume on up closes and
    subtracts it on down closes, starting from a zero baseline."""

    @property
    def name(self) -> str:
        return "obv"

    @property
    def warmup_period(self) -> int:
        return 1

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(f"{self.name} needs at least 1 candle, got {len(candles)}")
        obv = Decimal(0)
        points = [IndicatorPoint(timestamp=candles[0].timestamp, values={"obv": obv})]
        for index in range(1, len(candles)):
            if candles[index].close > candles[index - 1].close:
                obv += candles[index].volume
            elif candles[index].close < candles[index - 1].close:
                obv -= candles[index].volume
            points.append(IndicatorPoint(timestamp=candles[index].timestamp, values={"obv": obv}))
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=tuple(points))


class ChaikinMoneyFlowIndicator(Indicator):
    """Chaikin Money Flow: volume-weighted average of the close's position
    within each candle's high/low range, over a rolling window."""

    def __init__(self, period: int = 20) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = period

    @property
    def name(self) -> str:
        return f"cmf_{self._period}"

    @property
    def warmup_period(self) -> int:
        return self._period

    def compute(self, candles: Sequence[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"{self.name} needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        period = self._period
        money_flow_volumes: list[Decimal] = []
        for candle in candles:
            price_range = candle.high - candle.low
            if price_range == 0:
                multiplier = Decimal(0)  # doji/no-range candle contributes no money flow
            else:
                multiplier = ((candle.close - candle.low) - (candle.high - candle.close)) / price_range
            money_flow_volumes.append(multiplier * candle.volume)

        points: list[IndicatorPoint] = []
        for index in range(period - 1, len(candles)):
            window_candles = candles[index - period + 1 : index + 1]
            window_mfv = money_flow_volumes[index - period + 1 : index + 1]
            window_volume = sum((candle.volume for candle in window_candles), start=Decimal(0))
            if window_volume == 0:
                # No volume at all in the window — CMF undefined, omit the point.
                continue
            cmf = sum(window_mfv, start=Decimal(0)) / window_volume
            points.append(IndicatorPoint(timestamp=candles[index].timestamp, values={"cmf": cmf}))
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=tuple(points))
