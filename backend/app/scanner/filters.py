"""Deterministic scanner filters.

Rather than one bespoke class per named concept in the spec (price, RSI
range, ATR range, ...), most of those are expressed as configured instances
of two generic filters (``IndicatorRangeFilter`` for any single-valued
indicator, ``MovingAverageAlignmentFilter`` for trend/MA-relationship
checks) plus a few filters over the raw candle itself (price, volume,
liquidity). No AI is involved in eligibility — every filter here is a plain
comparison.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol

from backend.app.scanner.types import FilterOutcome, ScanContext, latest_single_indicator_value


class Filter(Protocol):
    """Something a ``Scanner`` can evaluate against one symbol's context."""

    @property
    def name(self) -> str: ...

    def evaluate(self, context: ScanContext) -> FilterOutcome: ...


class PriceRangeFilter:
    """Blocks symbols whose latest close is outside [min_price, max_price]."""

    def __init__(self, *, min_price: Decimal | None = None, max_price: Decimal | None = None) -> None:
        self._min_price = min_price
        self._max_price = max_price

    @property
    def name(self) -> str:
        return "price_range"

    def evaluate(self, context: ScanContext) -> FilterOutcome:
        price = context.latest_candle.close
        if self._min_price is not None and price < self._min_price:
            return FilterOutcome(passed=False, reason=f"price {price} below minimum {self._min_price}")
        if self._max_price is not None and price > self._max_price:
            return FilterOutcome(passed=False, reason=f"price {price} above maximum {self._max_price}")
        return FilterOutcome(passed=True)


class MinimumVolumeFilter:
    """Blocks symbols whose latest raw volume is below a floor."""

    def __init__(self, min_volume: Decimal) -> None:
        self._min_volume = min_volume

    @property
    def name(self) -> str:
        return "minimum_volume"

    def evaluate(self, context: ScanContext) -> FilterOutcome:
        volume = context.latest_candle.volume
        if volume < self._min_volume:
            return FilterOutcome(passed=False, reason=f"volume {volume} below minimum {self._min_volume}")
        return FilterOutcome(passed=True)


class LiquidityFilter:
    """Basic liquidity eligibility: close price * volume (dollar volume)
    must meet a floor."""

    def __init__(self, min_dollar_volume: Decimal) -> None:
        self._min_dollar_volume = min_dollar_volume

    @property
    def name(self) -> str:
        return "liquidity"

    def evaluate(self, context: ScanContext) -> FilterOutcome:
        dollar_volume = context.latest_candle.close * context.latest_candle.volume
        if dollar_volume < self._min_dollar_volume:
            return FilterOutcome(
                passed=False,
                reason=f"dollar volume {dollar_volume} below minimum {self._min_dollar_volume}",
            )
        return FilterOutcome(passed=True)


class IndicatorRangeFilter:
    """Blocks symbols whose latest value of a named indicator field falls
    outside [min_value, max_value]. Covers RSI/momentum ranges, volatility
    (ATR) constraints, and relative-volume minimums — anything expressed as
    "this indicator's latest value must be within a range"."""

    def __init__(
        self,
        indicator_name: str,
        value_key: str,
        *,
        min_value: Decimal | None = None,
        max_value: Decimal | None = None,
    ) -> None:
        self._indicator_name = indicator_name
        self._value_key = value_key
        self._min_value = min_value
        self._max_value = max_value

    @property
    def name(self) -> str:
        return f"{self._indicator_name}_{self._value_key}_range"

    def evaluate(self, context: ScanContext) -> FilterOutcome:
        result = context.indicators.get(self._indicator_name)
        if result is None or result.latest is None:
            return FilterOutcome(passed=False, reason=f"missing indicator data for {self._indicator_name}")
        value = result.latest.values.get(self._value_key)
        if value is None:
            return FilterOutcome(
                passed=False, reason=f"{self._indicator_name} has no value '{self._value_key}'"
            )
        if self._min_value is not None and value < self._min_value:
            return FilterOutcome(passed=False, reason=f"{self.name}: {value} below minimum {self._min_value}")
        if self._max_value is not None and value > self._max_value:
            return FilterOutcome(passed=False, reason=f"{self.name}: {value} above maximum {self._max_value}")
        return FilterOutcome(passed=True)


class MovingAverageAlignmentFilter:
    """Blocks symbols where two single-valued indicators (typically two
    moving averages) aren't in the required trend relationship.

    Both indicators must be single-valued (one entry in ``values``, e.g. an
    EMA/SMA's ``"ema"``/``"sma"`` key) — the specific key name is not
    assumed, only that there is exactly one.
    """

    def __init__(
        self,
        fast_indicator: str,
        slow_indicator: str,
        *,
        direction: Literal["above", "below"] = "above",
    ) -> None:
        self._fast_indicator = fast_indicator
        self._slow_indicator = slow_indicator
        self._direction = direction

    @property
    def name(self) -> str:
        return f"ma_alignment_{self._fast_indicator}_{self._direction}_{self._slow_indicator}"

    def evaluate(self, context: ScanContext) -> FilterOutcome:
        fast_value = latest_single_indicator_value(context.indicators, self._fast_indicator)
        slow_value = latest_single_indicator_value(context.indicators, self._slow_indicator)
        if fast_value is None or slow_value is None:
            return FilterOutcome(
                passed=False,
                reason=f"missing indicator data for {self._fast_indicator} or {self._slow_indicator}",
            )
        if self._direction == "above" and fast_value <= slow_value:
            return FilterOutcome(
                passed=False,
                reason=(
                    f"{self.name}: {self._fast_indicator} ({fast_value}) not above "
                    f"{self._slow_indicator} ({slow_value})"
                ),
            )
        if self._direction == "below" and fast_value >= slow_value:
            return FilterOutcome(
                passed=False,
                reason=(
                    f"{self.name}: {self._fast_indicator} ({fast_value}) not below "
                    f"{self._slow_indicator} ({slow_value})"
                ),
            )
        return FilterOutcome(passed=True)
