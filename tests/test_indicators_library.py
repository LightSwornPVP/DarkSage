"""Tests for the Phase 1 core technical indicator library.

Every known-value test uses inputs chosen so the expected Decimal result is
exact (no repeating-decimal rounding), so assertions are exact equality,
not approximate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.indicators.errors import InsufficientDataError
from backend.app.indicators.library import (
    ATRIndicator,
    AverageVolumeIndicator,
    BollingerBandsIndicator,
    ChaikinMoneyFlowIndicator,
    EMAIndicator,
    MACDIndicator,
    OBVIndicator,
    RSIIndicator,
    RelativeVolumeIndicator,
    SMAIndicator,
    VolumeIndicator,
    WilliamsPercentRIndicator,
    build_default_registry,
)
from shared.models.candle import Candle, Timeframe

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(
    day_offset: int,
    *,
    open: str,
    high: str,
    low: str,
    close: str,
    volume: str,
) -> Candle:
    return Candle(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=BASE + timedelta(days=day_offset),
        open=Decimal(open),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
    )


def _simple_series(closes: list[str]) -> list[Candle]:
    """Candles whose high/low bracket the close so OHLC validation passes,
    for indicators that only care about closing price."""
    offset = Decimal("0.1")
    return [
        _candle(
            i,
            open=c,
            high=str(Decimal(c) + offset),
            low=str(Decimal(c) - offset),
            close=c,
            volume="1000",
        )
        for i, c in enumerate(closes)
    ]


# --- SMA / EMA ---


def test_sma_known_values() -> None:
    candles = _simple_series(["1", "2", "3", "4", "5"])
    result = SMAIndicator(3).compute(candles)
    assert [p.values["sma"] for p in result.points] == [Decimal("2"), Decimal("3"), Decimal("4")]


def test_ema_known_values() -> None:
    candles = _simple_series(["10", "20", "30", "40", "50"])
    result = EMAIndicator(4).compute(candles)
    assert result.points[0].values["ema"] == Decimal("25")
    assert result.points[1].values["ema"] == Decimal("35")


def test_sma_raises_on_insufficient_data() -> None:
    with pytest.raises(InsufficientDataError):
        SMAIndicator(3).compute(_simple_series(["1", "2"]))


# --- RSI ---


def test_rsi_known_value() -> None:
    # changes: +4,-1,+4,-1 -> avg_gain=2, avg_loss=0.5 -> RS=4 -> RSI=100-100/5=80
    candles = _simple_series(["100", "104", "103", "107", "106"])
    result = RSIIndicator(4).compute(candles)
    assert len(result.points) == 1
    assert result.points[0].values["rsi"] == Decimal("80")


def test_rsi_all_gains_is_100() -> None:
    candles = _simple_series(["100", "101", "102", "103", "104"])
    result = RSIIndicator(4).compute(candles)
    assert result.points[0].values["rsi"] == Decimal("100")


def test_rsi_raises_on_insufficient_data() -> None:
    with pytest.raises(InsufficientDataError):
        RSIIndicator(4).compute(_simple_series(["1", "2", "3"]))


# --- MACD ---


def test_macd_is_deterministic_and_produces_points() -> None:
    closes = [str(100 + i) for i in range(40)]
    candles = _simple_series(closes)
    indicator = MACDIndicator(fast=3, slow=6, signal=2)

    first = indicator.compute(candles)
    second = indicator.compute(candles)

    assert first == second
    assert len(first.points) == len(candles) - indicator.warmup_period + 1
    for point in first.points:
        assert set(point.values) == {"macd", "signal", "histogram"}


def test_macd_raises_on_insufficient_data() -> None:
    indicator = MACDIndicator(fast=3, slow=6, signal=2)
    with pytest.raises(InsufficientDataError):
        indicator.compute(_simple_series([str(i) for i in range(1, 6)]))


def test_macd_rejects_fast_not_less_than_slow() -> None:
    with pytest.raises(ValueError):
        MACDIndicator(fast=10, slow=10, signal=2)


# --- Bollinger Bands ---


def test_bollinger_flat_prices_have_zero_width() -> None:
    candles = _simple_series(["10", "10", "10", "10"])
    result = BollingerBandsIndicator(4, 2).compute(candles)
    point = result.points[0]
    assert point.values["middle"] == Decimal("10")
    assert point.values["upper"] == Decimal("10")
    assert point.values["lower"] == Decimal("10")


# --- ATR ---


def test_atr_known_value() -> None:
    candles = [
        _candle(0, open="100", high="101", low="99", close="100", volume="1"),
        _candle(1, open="100", high="103", low="100", close="102", volume="1"),
        _candle(2, open="102", high="104", low="101", close="103", volume="1"),
    ]
    result = ATRIndicator(2).compute(candles)
    assert len(result.points) == 1
    assert result.points[0].values["atr"] == Decimal("3")


# --- Volume / AverageVolume / RVOL ---


def test_volume_passthrough() -> None:
    candles = _simple_series(["1", "2"])
    result = VolumeIndicator().compute(candles)
    assert [p.values["volume"] for p in result.points] == [Decimal("1000"), Decimal("1000")]


def test_average_volume_known_value() -> None:
    candles = [
        _candle(i, open="10", high="11", low="9", close="10", volume=v)
        for i, v in enumerate(["100", "200", "300"])
    ]
    result = AverageVolumeIndicator(2).compute(candles)
    assert [p.values["avg_volume"] for p in result.points] == [Decimal("150"), Decimal("250")]


def test_relative_volume_known_value() -> None:
    candles = [
        _candle(i, open="10", high="11", low="9", close="10", volume=v)
        for i, v in enumerate(["100", "200", "300"])
    ]
    result = RelativeVolumeIndicator(2).compute(candles)
    assert len(result.points) == 1
    assert result.points[0].values["rvol"] == Decimal("2")


# --- OBV ---


def test_obv_known_values() -> None:
    candles = [
        _candle(0, open="10", high="11", low="9", close="10", volume="100"),
        _candle(1, open="10", high="13", low="9", close="12", volume="200"),
        _candle(2, open="12", high="12", low="10", close="11", volume="300"),
        _candle(3, open="11", high="14", low="10", close="13", volume="400"),
    ]
    result = OBVIndicator().compute(candles)
    assert [p.values["obv"] for p in result.points] == [
        Decimal("0"),
        Decimal("200"),
        Decimal("-100"),
        Decimal("300"),
    ]


# --- Chaikin Money Flow ---


def test_cmf_known_value() -> None:
    candles = [
        _candle(0, open="9", high="10", low="8", close="9", volume="100"),
        _candle(1, open="9", high="12", low="8", close="11", volume="100"),
    ]
    result = ChaikinMoneyFlowIndicator(2).compute(candles)
    assert len(result.points) == 1
    assert result.points[0].values["cmf"] == Decimal("0.25")


# --- Williams %R ---


def test_williams_r_known_value() -> None:
    candles = [
        _candle(0, open="9", high="10", low="8", close="9", volume="1"),
        _candle(1, open="10", high="12", low="9", close="11", volume="1"),
    ]
    result = WilliamsPercentRIndicator(2).compute(candles)
    assert len(result.points) == 1
    assert result.points[0].values["williams_r"] == Decimal("-25")


def test_williams_r_omits_flat_range_point() -> None:
    # Zero-range bars (open == high == low == close) for every candle in the
    # window -> highest_high == lowest_low -> %R is undefined and omitted.
    candles = [
        _candle(i, open="10", high="10", low="10", close="10", volume="1") for i in range(3)
    ]
    result = WilliamsPercentRIndicator(2).compute(candles)
    assert result.points == ()


# --- Default registry wiring ---


def test_build_default_registry_has_no_duplicate_names() -> None:
    registry = build_default_registry()
    names = registry.names()
    assert len(names) == len(set(names))
    assert "rsi_14" in names
    assert "ema_9" in names
    assert "sma_200" in names
