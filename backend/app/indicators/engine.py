"""``IndicatorEngine`` — validates a candle series once, then runs one or
more registered indicators over it.

Provider-independent and renderer-independent: it only knows about
``Candle`` (shared/models) and ``Indicator``/``IndicatorRegistry`` (this
package). It must power charts, scanner, backtesting, and strategies alike
(ARCHITECTURE.md Section 8) — nothing here may assume a specific consumer.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.indicators.errors import InvalidCandleSeriesError
from backend.app.indicators.registry import IndicatorRegistry
from backend.app.indicators.types import IndicatorResult
from shared.models.candle import Candle


def validate_candle_series(candles: Sequence[Candle]) -> None:
    """Fail closed on any candle series an indicator cannot safely compute
    over: empty, mixed symbol, mixed timeframe, or non-increasing timestamps
    (which would otherwise let an indicator silently look ahead or double
    count a bar)."""
    if not candles:
        raise InvalidCandleSeriesError("candle series is empty")

    symbols = {candle.symbol for candle in candles}
    if len(symbols) > 1:
        raise InvalidCandleSeriesError(f"candle series mixes multiple symbols: {sorted(symbols)}")

    timeframes = {candle.timeframe for candle in candles}
    if len(timeframes) > 1:
        raise InvalidCandleSeriesError(
            f"candle series mixes multiple timeframes: {sorted(t.value for t in timeframes)}"
        )

    for previous, current in zip(candles, candles[1:], strict=False):
        if current.timestamp <= previous.timestamp:
            raise InvalidCandleSeriesError(
                "candle series must be strictly ordered by ascending timestamp "
                f"with no duplicates (found {previous.timestamp} then {current.timestamp})"
            )


class IndicatorEngine:
    """Runs registered indicators over a validated candle series."""

    def __init__(self, registry: IndicatorRegistry | None = None) -> None:
        self._registry = registry if registry is not None else IndicatorRegistry()

    @property
    def registry(self) -> IndicatorRegistry:
        return self._registry

    def compute(self, name: str, candles: Sequence[Candle]) -> IndicatorResult:
        validate_candle_series(candles)
        indicator = self._registry.get(name)
        return indicator.compute(candles)

    def compute_all(self, candles: Sequence[Candle]) -> dict[str, IndicatorResult]:
        validate_candle_series(candles)
        return {name: self._registry.get(name).compute(candles) for name in self._registry.names()}
