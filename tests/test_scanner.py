"""Tests for the scanner foundation: fail-safe behavior, filters, and
deterministic evaluation over a small synthetic universe."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.indicators.engine import IndicatorEngine
from backend.app.indicators.library import RSIIndicator, SMAIndicator
from backend.app.indicators.registry import IndicatorRegistry
from backend.app.scanner.filters import (
    IndicatorRangeFilter,
    LiquidityFilter,
    MinimumVolumeFilter,
    MovingAverageAlignmentFilter,
    PriceRangeFilter,
)
from backend.app.scanner.scanner import Scanner
from shared.models.candle import Candle, Timeframe

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(day_offset: int, close: str, volume: str = "1000000", *, symbol: str = "AAPL") -> Candle:
    price = Decimal(close)
    margin = Decimal("0.5")
    return Candle(
        symbol=symbol,
        timeframe=Timeframe.D1,
        timestamp=BASE + timedelta(days=day_offset),
        open=price,
        high=price + margin,
        low=price - margin,
        close=price,
        volume=Decimal(volume),
    )


def _uptrend(symbol: str = "AAPL", n: int = 10, start: int = 100) -> list[Candle]:
    return [_candle(i, str(start + i), symbol=symbol) for i in range(n)]


# A trending-but-not-monotonic series: pure +1-per-day price action saturates
# RSI at exactly 100 (no losses at all), which would fail the RSI range
# filter used below — these small pullbacks keep RSI inside (1, 99).
_MIXED_UPTREND_CLOSES = ["100", "102", "101", "103", "102", "104", "103", "105", "104", "106"]


def _mixed_uptrend(symbol: str = "AAPL") -> list[Candle]:
    return [_candle(i, close, symbol=symbol) for i, close in enumerate(_MIXED_UPTREND_CLOSES)]


def _build_scanner(**scanner_kwargs: object) -> Scanner:
    registry = IndicatorRegistry()
    registry.register(SMAIndicator(2))
    registry.register(SMAIndicator(4))
    registry.register(RSIIndicator(4))
    engine = IndicatorEngine(registry)
    filters = [
        PriceRangeFilter(min_price=Decimal("1")),
        MinimumVolumeFilter(Decimal("500000")),
        LiquidityFilter(Decimal("1000")),
        IndicatorRangeFilter("rsi_4", "rsi", min_value=Decimal("1"), max_value=Decimal("99")),
        MovingAverageAlignmentFilter("sma_2", "sma_4", direction="above"),
    ]
    kwargs: dict[str, object] = dict(indicator_names=["sma_2", "sma_4", "rsi_4"], filters=filters)
    kwargs.update(scanner_kwargs)
    return Scanner(engine, **kwargs)  # type: ignore[arg-type]


def test_uptrending_liquid_symbol_is_eligible() -> None:
    scanner = _build_scanner()
    result = scanner.scan({"AAPL": _mixed_uptrend()})
    candidate = result.candidates[0]
    assert candidate.eligible is True
    assert candidate.block_reasons == ()


def test_scan_result_eligible_property_filters_candidates() -> None:
    scanner = _build_scanner()
    result = scanner.scan({"AAPL": _mixed_uptrend(), "OTHER": _mixed_uptrend("OTHER")})
    assert {c.symbol for c in result.eligible} == {"AAPL", "OTHER"}


def test_scan_fails_safe_on_missing_data() -> None:
    scanner = _build_scanner()
    result = scanner.scan({"EMPTY": []})
    candidate = result.candidates[0]
    assert candidate.eligible is False
    assert candidate.latest_candle is None
    assert any("missing_data" in reason for reason in candidate.block_reasons)


def test_scan_fails_safe_on_invalid_data() -> None:
    scanner = _build_scanner()
    candles = _uptrend()
    reversed_candles = list(reversed(candles))  # non-increasing timestamps
    result = scanner.scan({"BAD": reversed_candles})
    candidate = result.candidates[0]
    assert candidate.eligible is False
    assert any("invalid_data" in reason for reason in candidate.block_reasons)


def test_scan_fails_safe_on_insufficient_history() -> None:
    scanner = _build_scanner()
    result = scanner.scan({"SHORT": _uptrend(n=2)})  # sma_4/rsi_4 need more than 2 candles
    candidate = result.candidates[0]
    assert candidate.eligible is False
    assert any("insufficient_history" in reason for reason in candidate.block_reasons)


def test_scan_fails_safe_on_stale_data() -> None:
    scanner = _build_scanner(
        max_data_age=timedelta(days=1),
        clock=lambda: BASE + timedelta(days=100),
    )
    result = scanner.scan({"AAPL": _uptrend()})
    candidate = result.candidates[0]
    assert candidate.eligible is False
    assert any("stale_data" in reason for reason in candidate.block_reasons)


def test_price_range_filter_blocks_low_price() -> None:
    scanner = _build_scanner(filters=[PriceRangeFilter(min_price=Decimal("500"))], indicator_names=[])
    result = scanner.scan({"AAPL": _uptrend()})
    candidate = result.candidates[0]
    assert candidate.eligible is False
    assert any("below minimum" in reason for reason in candidate.block_reasons)


def test_minimum_volume_filter_blocks_low_volume() -> None:
    candles = [_candle(i, str(100 + i), volume="1") for i in range(5)]
    scanner = _build_scanner(filters=[MinimumVolumeFilter(Decimal("1000"))], indicator_names=[])
    result = scanner.scan({"LOWVOL": candles})
    assert result.candidates[0].eligible is False


def test_moving_average_alignment_blocks_downtrend() -> None:
    scanner = _build_scanner()
    downtrend = [_candle(i, str(120 - i)) for i in range(10)]
    result = scanner.scan({"DOWN": downtrend})
    candidate = result.candidates[0]
    assert candidate.eligible is False
    assert any("ma_alignment" in reason for reason in candidate.block_reasons)


def test_scan_is_deterministic() -> None:
    scanner = _build_scanner()
    universe = {"AAPL": _uptrend()}
    first = scanner.scan(universe)
    second = scanner.scan(universe)
    assert first == second
