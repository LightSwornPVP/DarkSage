"""Deterministic scanner scoring — an explainable heuristic, not a
probability, and never an eligibility decision.

Hard blockers always win: ``ScanScorer.rank`` only ever returns candidates
that were already eligible after filtering (Slice 1.9). A component here
can push a score up or down, but it can never make an ineligible candidate
rank, and it never decides eligibility itself — that stays entirely in
``Scanner``/``Filter``. No AI is involved; every component is a plain,
documented formula over already-computed indicator values.

Each component uses one of the Phase 1-supported dimensions that actually
exist in this codebase: trend/structure (moving-average spread), momentum
(RSI), volume/participation (RVOL), volatility/context (ATR relative to
price), and liquidity/data quality (dollar volume versus a floor). This is
deliberately not the full future 0-1000 production scoring system — just
enough signal to support ranking now.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol

from backend.app.scanner.types import (
    ScanCandidate,
    ScanResult,
    ScanScore,
    ScoreComponent,
    latest_single_indicator_value,
)


class ScoreComponentFn(Protocol):
    """One named, weighted contribution to a candidate's score."""

    @property
    def name(self) -> str: ...

    @property
    def weight(self) -> Decimal: ...

    def compute(self, candidate: ScanCandidate) -> Decimal | None:
        """Return this component's raw value, or None if the candidate's
        data can't support it (never a fabricated 0)."""


class TrendStructureComponent:
    """Percentage spread between a fast and slow moving average — positive
    means the fast average is above the slow one (bullish structure)."""

    def __init__(self, fast_indicator: str, slow_indicator: str, *, weight: Decimal = Decimal(1)) -> None:
        self._fast_indicator = fast_indicator
        self._slow_indicator = slow_indicator
        self.weight = weight

    @property
    def name(self) -> str:
        return f"trend_{self._fast_indicator}_{self._slow_indicator}"

    def compute(self, candidate: ScanCandidate) -> Decimal | None:
        fast_value = latest_single_indicator_value(candidate.indicators, self._fast_indicator)
        slow_value = latest_single_indicator_value(candidate.indicators, self._slow_indicator)
        if fast_value is None or slow_value is None or slow_value == 0:
            return None
        return (fast_value - slow_value) / slow_value * Decimal(100)


class MomentumComponent:
    """RSI centered on 50: positive means bullish momentum, negative bearish."""

    def __init__(self, rsi_indicator: str, *, weight: Decimal = Decimal(1)) -> None:
        self._rsi_indicator = rsi_indicator
        self.weight = weight

    @property
    def name(self) -> str:
        return f"momentum_{self._rsi_indicator}"

    def compute(self, candidate: ScanCandidate) -> Decimal | None:
        result = candidate.indicators.get(self._rsi_indicator)
        if result is None or result.latest is None:
            return None
        rsi = result.latest.values.get("rsi")
        if rsi is None:
            return None
        return rsi - Decimal(50)


class VolumeParticipationComponent:
    """RVOL expressed as a percentage above/below its own baseline (RVOL=1)."""

    def __init__(self, rvol_indicator: str, *, weight: Decimal = Decimal(1)) -> None:
        self._rvol_indicator = rvol_indicator
        self.weight = weight

    @property
    def name(self) -> str:
        return f"volume_{self._rvol_indicator}"

    def compute(self, candidate: ScanCandidate) -> Decimal | None:
        result = candidate.indicators.get(self._rvol_indicator)
        if result is None or result.latest is None:
            return None
        rvol = result.latest.values.get("rvol")
        if rvol is None:
            return None
        return (rvol - Decimal(1)) * Decimal(100)


class VolatilityContextComponent:
    """ATR as a percentage of price, applied as a penalty.

    This is a deliberate, documented convention for this Phase 1 scorer —
    more relative volatility is treated as more risk, not more opportunity.
    A strategy that wants the opposite bias can pass a negative weight.
    """

    def __init__(self, atr_indicator: str, *, weight: Decimal = Decimal(1)) -> None:
        self._atr_indicator = atr_indicator
        self.weight = weight

    @property
    def name(self) -> str:
        return f"volatility_{self._atr_indicator}"

    def compute(self, candidate: ScanCandidate) -> Decimal | None:
        if candidate.latest_candle is None or candidate.latest_candle.close == 0:
            return None
        result = candidate.indicators.get(self._atr_indicator)
        if result is None or result.latest is None:
            return None
        atr = result.latest.values.get("atr")
        if atr is None:
            return None
        atr_percent_of_price = atr / candidate.latest_candle.close * Decimal(100)
        return -atr_percent_of_price


class LiquidityQualityComponent:
    """How far above a liquidity floor (dollar volume) a candidate sits,
    capped so an extreme outlier can't dominate the total score."""

    def __init__(
        self, min_dollar_volume: Decimal, *, cap: Decimal = Decimal(5), weight: Decimal = Decimal(1)
    ) -> None:
        if min_dollar_volume <= 0:
            raise ValueError("min_dollar_volume must be > 0")
        self._min_dollar_volume = min_dollar_volume
        self._cap = cap
        self.weight = weight

    @property
    def name(self) -> str:
        return "liquidity_quality"

    def compute(self, candidate: ScanCandidate) -> Decimal | None:
        if candidate.latest_candle is None:
            return None
        dollar_volume = candidate.latest_candle.close * candidate.latest_candle.volume
        return min(dollar_volume / self._min_dollar_volume, self._cap)


class ScanScorer:
    """Applies a fixed set of score components to scan candidates."""

    def __init__(self, components: Sequence[ScoreComponentFn]) -> None:
        self._components = tuple(components)

    def score(self, candidate: ScanCandidate) -> ScanScore:
        computed: list[ScoreComponent] = []
        for component in self._components:
            value = component.compute(candidate)
            if value is None:
                continue
            computed.append(
                ScoreComponent(
                    name=component.name,
                    value=value,
                    weight=component.weight,
                    weighted_value=value * component.weight,
                )
            )
        total_score = (
            sum((component.weighted_value for component in computed), start=Decimal(0)) if computed else None
        )
        return ScanScore(
            symbol=candidate.symbol,
            eligible=candidate.eligible,
            block_reasons=candidate.block_reasons,
            components=tuple(computed),
            total_score=total_score,
        )

    def score_all(self, result: ScanResult) -> tuple[ScanScore, ...]:
        return tuple(self.score(candidate) for candidate in result.candidates)

    def rank(self, result: ScanResult) -> tuple[ScanScore, ...]:
        """Ranking support: only eligible candidates are returned — a hard
        blocker always overrides any score, so a blocked candidate never
        appears here no matter how high its underlying score would be.
        Sorted by total_score descending; a None score (no components could
        be computed) sorts last.
        """
        eligible_scores = [scan_score for scan_score in self.score_all(result) if scan_score.eligible]
        return tuple(
            sorted(
                eligible_scores,
                key=lambda scan_score: (
                    scan_score.total_score is None,
                    -(scan_score.total_score if scan_score.total_score is not None else Decimal(0)),
                ),
            )
        )
