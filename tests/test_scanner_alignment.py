"""Regression tests for blocker 6: indicator values consumed for scanner
eligibility/scoring must align with the latest candle's timestamp — a
stale, older indicator point must never be silently reused."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.indicators.engine import IndicatorEngine
from backend.app.indicators.library.momentum import WilliamsPercentRIndicator
from backend.app.indicators.registry import IndicatorRegistry
from backend.app.indicators.types import IndicatorPoint, IndicatorResult
from backend.app.scanner.filters import IndicatorRangeFilter
from backend.app.scanner.scanner import Scanner
from backend.app.scanner.scoring import ScanScorer, VolumeParticipationComponent
from backend.app.scanner.types import (
    ScanCandidate,
    ScanContext,
    current_indicator_point,
    latest_single_indicator_value,
)
from shared.models.candle import Candle, Timeframe

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
YESTERDAY = NOW - timedelta(days=1)


def _candle(day_offset: int, close: str, volume: str = "1000000", *, symbol: str = "AAPL") -> Candle:
    price = Decimal(close)
    return Candle(
        symbol=symbol,
        timeframe=Timeframe.D1,
        timestamp=NOW + timedelta(days=day_offset),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=Decimal(volume),
    )


# --- current_indicator_point: the shared alignment primitive ---


def test_current_indicator_point_accepts_point_matching_latest_candle() -> None:
    latest = _candle(0, "100")
    result = IndicatorResult(
        name="x",
        timeframe=Timeframe.D1,
        points=(IndicatorPoint(timestamp=latest.timestamp, values={"v": Decimal(1)}),),
    )
    point = current_indicator_point({"x": result}, "x", latest)
    assert point is not None
    assert point.values["v"] == Decimal(1)


def test_current_indicator_point_rejects_older_point() -> None:
    latest = _candle(1, "101")
    stale_result = IndicatorResult(
        name="x", timeframe=Timeframe.D1, points=(IndicatorPoint(timestamp=YESTERDAY, values={"v": Decimal(1)}),)
    )
    assert current_indicator_point({"x": stale_result}, "x", latest) is None


def test_current_indicator_point_rejects_missing_indicator() -> None:
    latest = _candle(0, "100")
    assert current_indicator_point({}, "x", latest) is None


def test_current_indicator_point_rejects_empty_points() -> None:
    latest = _candle(0, "100")
    empty_result = IndicatorResult(name="x", timeframe=Timeframe.D1, points=())
    assert current_indicator_point({"x": empty_result}, "x", latest) is None


def test_latest_single_indicator_value_uses_same_alignment_rule() -> None:
    latest = _candle(1, "101")
    stale_result = IndicatorResult(
        name="x", timeframe=Timeframe.D1, points=(IndicatorPoint(timestamp=YESTERDAY, values={"ema": Decimal(1)}),)
    )
    assert latest_single_indicator_value({"x": stale_result}, "x", latest) is None


# --- Real omission scenario: Williams %R can skip the current candle ---


def test_scanner_treats_omitted_current_williams_r_as_unavailable_not_stale() -> None:
    candles = [
        Candle(
            symbol="ALIGN",
            timeframe=Timeframe.D1,
            timestamp=NOW + timedelta(days=i),
            open=Decimal(100),
            high=Decimal(100),
            low=Decimal(100),
            close=Decimal(100),
            volume=Decimal(1000),
        )
        for i in range(3)
    ]  # every candle is zero-range -> every Williams %R window is flat -> all points omitted

    registry = IndicatorRegistry()
    registry.register(WilliamsPercentRIndicator(2))
    engine = IndicatorEngine(registry)
    scanner = Scanner(
        engine,
        indicator_names=["williams_r_2"],
        filters=[
            IndicatorRangeFilter("williams_r_2", "williams_r", min_value=Decimal(-100), max_value=Decimal(0))
        ],
        allow_stale_data_for_testing=True,
    )

    result = scanner.scan({"ALIGN": candles})
    candidate = result.candidates[0]

    # The indicator computed successfully (no InsufficientDataError) but has
    # no point at the latest candle's timestamp — the filter must treat that
    # as unavailable, not silently reuse an older point or pass anyway.
    assert "williams_r_2" in candidate.indicators
    assert candidate.indicators["williams_r_2"].points == ()
    assert candidate.eligible is False
    assert any("missing current indicator data" in reason for reason in candidate.block_reasons)


def test_scoring_omits_component_when_rvol_point_is_stale_relative_to_latest_candle() -> None:
    latest_candle = _candle(5, "100", volume="500000")
    stale_rvol = IndicatorResult(
        name="rvol_3",
        timeframe=Timeframe.D1,
        points=(IndicatorPoint(timestamp=YESTERDAY, values={"rvol": Decimal("3")}),),  # not latest_candle's day
    )
    candidate = ScanCandidate(
        symbol="ALIGN",
        latest_candle=latest_candle,
        eligible=True,
        block_reasons=(),
        indicators={"rvol_3": stale_rvol},
    )
    scorer = ScanScorer([VolumeParticipationComponent("rvol_3")])
    score = scorer.score(candidate)

    # A huge RVOL=3 would produce a large positive component if reused; the
    # stale point must instead be skipped entirely (never fabricated as 0).
    assert score.components == ()
    assert score.total_score is None


def test_filtering_and_scoring_agree_on_the_same_stale_rvol_point() -> None:
    latest_candle = _candle(5, "100", volume="500000")
    stale_rvol = IndicatorResult(
        name="rvol_3",
        timeframe=Timeframe.D1,
        points=(IndicatorPoint(timestamp=YESTERDAY, values={"rvol": Decimal("3")}),),
    )
    indicators = {"rvol_3": stale_rvol}

    filter_outcome = IndicatorRangeFilter("rvol_3", "rvol", min_value=Decimal("0")).evaluate(
        ScanContext(symbol="ALIGN", latest_candle=latest_candle, indicators=indicators)
    )
    candidate = ScanCandidate(
        symbol="ALIGN", latest_candle=latest_candle, eligible=True, block_reasons=(), indicators=indicators
    )
    score = ScanScorer([VolumeParticipationComponent("rvol_3")]).score(candidate)

    assert filter_outcome.passed is False
    assert score.total_score is None
