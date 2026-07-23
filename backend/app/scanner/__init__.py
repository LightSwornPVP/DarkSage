"""Deterministic market scanner foundation (PROJECT_SPEC.md Section 5).

Scans a supplied universe using normalized candle data and indicator
outputs. No AI is required for broad-universe scanning, and no trading or
execution action is ever taken here.
"""

from backend.app.scanner.filters import (
    Filter,
    IndicatorRangeFilter,
    LiquidityFilter,
    MinimumVolumeFilter,
    MovingAverageAlignmentFilter,
    PriceRangeFilter,
)
from backend.app.scanner.scanner import Scanner
from backend.app.scanner.types import FilterOutcome, ScanCandidate, ScanContext, ScanResult

__all__ = [
    "Filter",
    "FilterOutcome",
    "IndicatorRangeFilter",
    "LiquidityFilter",
    "MinimumVolumeFilter",
    "MovingAverageAlignmentFilter",
    "PriceRangeFilter",
    "ScanCandidate",
    "ScanContext",
    "ScanResult",
    "Scanner",
]
