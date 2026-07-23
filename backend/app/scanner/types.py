"""Typed structures for the scanner foundation.

Eligibility (did this symbol pass every filter?) is kept structurally
separate from any future score/rank — this module only knows pass/fail and
why, never a numeric ranking (that arrives in Slice 1.10).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.app.indicators.types import IndicatorResult
from shared.models.candle import Candle


@dataclass(frozen=True, slots=True)
class ScanContext:
    """Everything a filter needs to evaluate one symbol."""

    symbol: str
    latest_candle: Candle
    indicators: Mapping[str, IndicatorResult]


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
