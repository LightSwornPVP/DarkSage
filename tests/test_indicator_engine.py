"""Tests for the indicator engine foundation: registry, validation, and the
Indicator/IndicatorEngine contract, using a trivial dummy indicator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.indicators.base import Indicator
from backend.app.indicators.engine import IndicatorEngine, validate_candle_series
from backend.app.indicators.errors import InsufficientDataError, InvalidCandleSeriesError
from backend.app.indicators.registry import IndicatorRegistry
from backend.app.indicators.types import IndicatorPoint, IndicatorResult
from shared.models.candle import Candle, Timeframe

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(day_offset: int, close: str, *, symbol: str = "AAPL", timeframe: Timeframe = Timeframe.D1) -> Candle:
    price = Decimal(close)
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=BASE + timedelta(days=day_offset),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=Decimal(1000),
    )


class _LastClose(Indicator):
    """Trivial indicator: echoes the close price. warmup_period=2 lets tests
    exercise both the insufficient-data path and the valid path."""

    @property
    def name(self) -> str:
        return "last_close"

    @property
    def warmup_period(self) -> int:
        return 2

    def compute(self, candles: list[Candle]) -> IndicatorResult:
        if len(candles) < self.warmup_period:
            raise InsufficientDataError(
                f"last_close needs at least {self.warmup_period} candles, got {len(candles)}"
            )
        points = tuple(
            IndicatorPoint(timestamp=c.timestamp, values={"close": c.close})
            for c in candles[self.warmup_period - 1 :]
        )
        return IndicatorResult(name=self.name, timeframe=candles[0].timeframe, points=points)


# --- Registry ---


def test_registry_register_and_get() -> None:
    registry = IndicatorRegistry()
    indicator = _LastClose()
    registry.register(indicator)
    assert registry.get("last_close") is indicator
    assert registry.names() == ("last_close",)
    assert "last_close" in registry


def test_registry_rejects_duplicate_registration() -> None:
    registry = IndicatorRegistry()
    registry.register(_LastClose())
    with pytest.raises(ValueError):
        registry.register(_LastClose())


def test_registry_unknown_name_raises_key_error() -> None:
    registry = IndicatorRegistry()
    with pytest.raises(KeyError):
        registry.get("does_not_exist")


# --- validate_candle_series ---


def test_validate_candle_series_rejects_empty() -> None:
    with pytest.raises(InvalidCandleSeriesError):
        validate_candle_series([])


def test_validate_candle_series_rejects_mixed_symbols() -> None:
    candles = [_candle(0, "100", symbol="AAPL"), _candle(1, "101", symbol="MSFT")]
    with pytest.raises(InvalidCandleSeriesError):
        validate_candle_series(candles)


def test_validate_candle_series_rejects_mixed_timeframes() -> None:
    candles = [_candle(0, "100", timeframe=Timeframe.D1), _candle(1, "101", timeframe=Timeframe.H1)]
    with pytest.raises(InvalidCandleSeriesError):
        validate_candle_series(candles)


def test_validate_candle_series_rejects_non_increasing_timestamps() -> None:
    candles = [_candle(1, "100"), _candle(0, "101")]
    with pytest.raises(InvalidCandleSeriesError):
        validate_candle_series(candles)


def test_validate_candle_series_rejects_duplicate_timestamps() -> None:
    c = _candle(0, "100")
    with pytest.raises(InvalidCandleSeriesError):
        validate_candle_series([c, c])


def test_validate_candle_series_accepts_valid_series() -> None:
    candles = [_candle(0, "100"), _candle(1, "101")]
    validate_candle_series(candles)  # no raise


# --- IndicatorEngine ---


def test_engine_compute_returns_expected_points() -> None:
    engine = IndicatorEngine()
    engine.registry.register(_LastClose())
    candles = [_candle(0, "100"), _candle(1, "101"), _candle(2, "102")]

    result = engine.compute("last_close", candles)

    assert result.name == "last_close"
    assert len(result.points) == 2  # warmup_period=2 -> first point skipped
    assert result.latest is not None
    assert result.latest.values["close"] == Decimal("102")


def test_engine_compute_raises_on_insufficient_data() -> None:
    engine = IndicatorEngine()
    engine.registry.register(_LastClose())
    with pytest.raises(InsufficientDataError):
        engine.compute("last_close", [_candle(0, "100")])


def test_engine_compute_validates_series_before_delegating() -> None:
    engine = IndicatorEngine()
    engine.registry.register(_LastClose())
    with pytest.raises(InvalidCandleSeriesError):
        engine.compute("last_close", [])


def test_engine_compute_all_runs_every_registered_indicator() -> None:
    engine = IndicatorEngine()
    engine.registry.register(_LastClose())
    candles = [_candle(0, "100"), _candle(1, "101")]
    results = engine.compute_all(candles)
    assert set(results) == {"last_close"}


def test_engine_compute_is_deterministic() -> None:
    engine = IndicatorEngine()
    engine.registry.register(_LastClose())
    candles = [_candle(0, "100"), _candle(1, "101"), _candle(2, "102")]

    first = engine.compute("last_close", candles)
    second = engine.compute("last_close", candles)

    assert first == second
