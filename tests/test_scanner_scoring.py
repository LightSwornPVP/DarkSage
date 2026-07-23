"""Tests for scanner scoring: component formulas, weighting, and the
separation between scoring and eligibility (hard blockers always win)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backend.app.indicators.types import IndicatorPoint, IndicatorResult
from backend.app.scanner.scoring import (
    LiquidityQualityComponent,
    MomentumComponent,
    ScanScorer,
    TrendStructureComponent,
    VolatilityContextComponent,
    VolumeParticipationComponent,
)
from backend.app.scanner.types import ScanCandidate, ScanResult
from shared.models.candle import Candle, Timeframe

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(close: str, volume: str) -> Candle:
    price = Decimal(close)
    return Candle(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=NOW,
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=Decimal(volume),
    )


def _indicator_result(name: str, key: str, value: str) -> IndicatorResult:
    return IndicatorResult(
        name=name,
        timeframe=Timeframe.D1,
        points=(IndicatorPoint(timestamp=NOW, values={key: Decimal(value)}),),
    )


def _candidate(
    *,
    symbol: str = "AAPL",
    close: str = "100",
    volume: str = "1000000",
    eligible: bool = True,
    block_reasons: tuple[str, ...] = (),
    indicators: dict[str, IndicatorResult] | None = None,
) -> ScanCandidate:
    return ScanCandidate(
        symbol=symbol,
        latest_candle=_candle(close, volume),
        eligible=eligible,
        block_reasons=block_reasons,
        indicators=indicators or {},
    )


# --- Individual components ---


def test_trend_structure_component_known_value() -> None:
    candidate = _candidate(
        indicators={
            "sma_fast": _indicator_result("sma_fast", "sma", "110"),
            "sma_slow": _indicator_result("sma_slow", "sma", "100"),
        }
    )
    component = TrendStructureComponent("sma_fast", "sma_slow")
    assert component.compute(candidate) == Decimal("10")


def test_momentum_component_known_value() -> None:
    candidate = _candidate(indicators={"rsi_14": _indicator_result("rsi_14", "rsi", "70")})
    component = MomentumComponent("rsi_14")
    assert component.compute(candidate) == Decimal("20")


def test_volume_participation_component_known_value() -> None:
    candidate = _candidate(indicators={"rvol_20": _indicator_result("rvol_20", "rvol", "1.5")})
    component = VolumeParticipationComponent("rvol_20")
    assert component.compute(candidate) == Decimal("50")


def test_volatility_context_component_is_a_penalty() -> None:
    candidate = _candidate(close="100", indicators={"atr_14": _indicator_result("atr_14", "atr", "2")})
    component = VolatilityContextComponent("atr_14")
    assert component.compute(candidate) == Decimal("-2")


def test_liquidity_quality_component_caps_extreme_values() -> None:
    candidate = _candidate(close="100", volume="1000000")  # dollar volume = 100,000,000
    component = LiquidityQualityComponent(Decimal("1000"), cap=Decimal(5))
    assert component.compute(candidate) == Decimal(5)


def test_component_returns_none_when_indicator_missing() -> None:
    candidate = _candidate(indicators={})
    assert MomentumComponent("rsi_14").compute(candidate) is None


# --- ScanScorer ---


def test_scorer_combines_weighted_components() -> None:
    candidate = _candidate(
        indicators={
            "rsi_14": _indicator_result("rsi_14", "rsi", "70"),  # momentum = 20
            "rvol_20": _indicator_result("rvol_20", "rvol", "2"),  # volume = 100
        }
    )
    scorer = ScanScorer(
        [MomentumComponent("rsi_14", weight=Decimal(2)), VolumeParticipationComponent("rvol_20", weight=Decimal("0.5"))]
    )
    score = scorer.score(candidate)
    assert score.total_score == Decimal("20") * 2 + Decimal("100") * Decimal("0.5")
    assert {c.name for c in score.components} == {"momentum_rsi_14", "volume_rvol_20"}


def test_scorer_skips_missing_components_without_fabricating_zero() -> None:
    candidate = _candidate(indicators={"rsi_14": _indicator_result("rsi_14", "rsi", "60")})
    scorer = ScanScorer([MomentumComponent("rsi_14"), VolumeParticipationComponent("rvol_20")])
    score = scorer.score(candidate)
    assert len(score.components) == 1
    assert score.total_score == Decimal("10")


def test_scorer_total_score_is_none_when_no_components_computed() -> None:
    candidate = _candidate(indicators={})
    scorer = ScanScorer([MomentumComponent("rsi_14")])
    score = scorer.score(candidate)
    assert score.components == ()
    assert score.total_score is None


# --- Hard blockers override scores; scoring != eligibility ---


def test_rank_excludes_ineligible_candidate_even_with_highest_score() -> None:
    blocked_but_high_score = _candidate(
        symbol="BLOCKED",
        eligible=False,
        block_reasons=("invalid_data: mixed symbols",),
        indicators={"rsi_14": _indicator_result("rsi_14", "rsi", "100")},  # momentum = 50, huge
    )
    eligible_lower_score = _candidate(
        symbol="OK", indicators={"rsi_14": _indicator_result("rsi_14", "rsi", "55")}
    )
    result = ScanResult(candidates=(blocked_but_high_score, eligible_lower_score))
    scorer = ScanScorer([MomentumComponent("rsi_14")])

    ranked = scorer.rank(result)

    assert [s.symbol for s in ranked] == ["OK"]  # BLOCKED never appears, regardless of score


def test_rank_is_deterministically_ordered_descending() -> None:
    low = _candidate(symbol="LOW", indicators={"rsi_14": _indicator_result("rsi_14", "rsi", "51")})
    high = _candidate(symbol="HIGH", indicators={"rsi_14": _indicator_result("rsi_14", "rsi", "90")})
    mid = _candidate(symbol="MID", indicators={"rsi_14": _indicator_result("rsi_14", "rsi", "60")})
    result = ScanResult(candidates=(low, high, mid))
    scorer = ScanScorer([MomentumComponent("rsi_14")])

    first = scorer.rank(result)
    second = scorer.rank(result)

    assert [s.symbol for s in first] == ["HIGH", "MID", "LOW"]
    assert first == second


def test_rank_sorts_none_scores_last() -> None:
    no_data = _candidate(symbol="NODATA", indicators={})
    scored = _candidate(symbol="SCORED", indicators={"rsi_14": _indicator_result("rsi_14", "rsi", "60")})
    result = ScanResult(candidates=(no_data, scored))
    scorer = ScanScorer([MomentumComponent("rsi_14")])

    ranked = scorer.rank(result)

    assert [s.symbol for s in ranked] == ["SCORED", "NODATA"]
