"""Deterministic indicator engine — see ARCHITECTURE.md Section 8.

Powers charts, scanner, backtesting, and strategies alike. No AI is used
for indicator math; every calculation here is local and deterministic.
"""

from backend.app.indicators.base import Indicator
from backend.app.indicators.engine import IndicatorEngine, validate_candle_series
from backend.app.indicators.errors import (
    IndicatorError,
    InsufficientDataError,
    InvalidCandleSeriesError,
)
from backend.app.indicators.registry import IndicatorRegistry
from backend.app.indicators.types import IndicatorPoint, IndicatorResult

__all__ = [
    "Indicator",
    "IndicatorEngine",
    "IndicatorError",
    "IndicatorPoint",
    "IndicatorRegistry",
    "IndicatorResult",
    "InsufficientDataError",
    "InvalidCandleSeriesError",
    "validate_candle_series",
]
