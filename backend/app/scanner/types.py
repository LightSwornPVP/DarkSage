"""Typed structures for the scanner foundation.

Eligibility (did this symbol pass every filter?) is kept structurally
separate from any future score/rank — this module only knows pass/fail and
why, never a numeric ranking (that arrives in Slice 1.10).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from backend.app.indicators.types import IndicatorPoint, IndicatorResult
from shared.models.candle import Candle


@dataclass(frozen=True, slots=True)
class ScanContext:
    """Everything a filter needs to evaluate one symbol."""

    symbol: str
    latest_candle: Candle
    indicators: Mapping[str, IndicatorResult]


def current_indicator_point(
    indicators: Mapping[str, IndicatorResult], indicator_name: str, latest_candle: Candle
) -> IndicatorPoint | None:
    """The indicator's value at exactly ``latest_candle``'s timestamp — the
    single alignment rule every filter and score component must use.

    Returns None (never an older point) if the indicator is missing, has no
    points, or its most recent computed point belongs to an earlier candle.
    Indicators like RVOL/CMF/Williams %R can legitimately omit a point for a
    degenerate current candle (e.g. a flat range); silently reusing their
    last *available* point would misrepresent a stale reading as current.
    """
    result = indicators.get(indicator_name)
    if result is None or not result.points:
        return None
    latest_point = result.points[-1]
    if latest_point.timestamp != latest_candle.timestamp:
        return None
    return latest_point


def latest_single_indicator_value(
    indicators: Mapping[str, IndicatorResult], indicator_name: str, latest_candle: Candle
) -> Decimal | None:
    """The current (latest-candle-aligned) value of a single-valued
    indicator (e.g. an EMA/SMA's one ``"ema"``/``"sma"`` entry), or None if
    unavailable — see ``current_indicator_point`` for the alignment rule.

    Shared by filters (``MovingAverageAlignmentFilter``) and scoring
    (``TrendStructureComponent``) so both read a moving average's current
    value the same way.
    """
    point = current_indicator_point(indicators, indicator_name, latest_candle)
    if point is None:
        return None
    return next(iter(point.values.values()), None)


@dataclass(frozen=True, slots=True)
class FilterOutcome:
    """The result of evaluating one filter against one ``ScanContext``."""

    passed: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ScanCandidate:
    """One symbol's scan outcome: eligible or blocked, and why.

    ``latest_candle``/``indicators`` are ``None``/empty when the symbol
    couldn't even be evaluated (missing, stale, or invalid data) — always
    check ``eligible`` first, and ``block_reasons`` explains any failure.
    """

    symbol: str
    latest_candle: Candle | None
    eligible: bool
    block_reasons: tuple[str, ...]
    indicators: Mapping[str, IndicatorResult]


@dataclass(frozen=True, slots=True)
class ScanResult:
    """The full output of scanning a universe."""

    candidates: tuple[ScanCandidate, ...]

    @property
    def eligible(self) -> tuple[ScanCandidate, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.eligible)


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    """One named, explainable contribution to a candidate's total score."""

    name: str
    value: Decimal
    weight: Decimal
    weighted_value: Decimal


@dataclass(frozen=True, slots=True)
class ScanScore:
    """A candidate's internal heuristic score, kept structurally separate
    from eligibility: ``eligible``/``block_reasons`` are copied straight
    from the ``ScanCandidate`` a hard blocker cannot be outweighed by a high
    score, and a high score never implies a probability of anything.

    ``total_score`` is ``None`` only when every component was skipped for
    missing data — never a fabricated 0.
    """

    symbol: str
    eligible: bool
    block_reasons: tuple[str, ...]
    components: tuple[ScoreComponent, ...]
    total_score: Decimal | None
