"""Typed structures for the scanner foundation.

Eligibility (did this symbol pass every filter?) is kept structurally
separate from any future score/rank — this module only knows pass/fail and
why, never a numeric ranking (that arrives in Slice 1.10).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from backend.app.indicators.types import IndicatorResult
from shared.models.candle import Candle


@dataclass(frozen=True, slots=True)
class ScanContext:
    """Everything a filter needs to evaluate one symbol."""

    symbol: str
    latest_candle: Candle
    indicators: Mapping[str, IndicatorResult]


def latest_single_indicator_value(
    indicators: Mapping[str, IndicatorResult], indicator_name: str
) -> Decimal | None:
    """The latest value of a single-valued indicator (e.g. an EMA/SMA's one
    ``"ema"``/``"sma"`` entry), or None if the indicator is missing, has no
    points, or the specific key isn't otherwise known.

    Shared by filters (``MovingAverageAlignmentFilter``) and scoring
    (``TrendStructureComponent``) so both read a moving average's latest
    value the same way.
    """
    result = indicators.get(indicator_name)
    if result is None or result.latest is None:
        return None
    return next(iter(result.latest.values.values()), None)


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
