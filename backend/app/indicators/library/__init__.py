"""Concrete Phase 1 core technical indicators (PROJECT_SPEC.md Section 5).

All deterministic and local — no AI is used for indicator math.
"""

from backend.app.indicators.library.momentum import MACDIndicator, RSIIndicator, WilliamsPercentRIndicator
from backend.app.indicators.library.moving_average import EMAIndicator, SMAIndicator
from backend.app.indicators.library.volatility import ATRIndicator, BollingerBandsIndicator
from backend.app.indicators.library.volume import (
    AverageVolumeIndicator,
    ChaikinMoneyFlowIndicator,
    OBVIndicator,
    RelativeVolumeIndicator,
    VolumeIndicator,
)
from backend.app.indicators.registry import IndicatorRegistry

__all__ = [
    "ATRIndicator",
    "AverageVolumeIndicator",
    "BollingerBandsIndicator",
    "ChaikinMoneyFlowIndicator",
    "EMAIndicator",
    "MACDIndicator",
    "OBVIndicator",
    "RSIIndicator",
    "RelativeVolumeIndicator",
    "SMAIndicator",
    "VolumeIndicator",
    "WilliamsPercentRIndicator",
    "build_default_registry",
]


def build_default_registry() -> IndicatorRegistry:
    """A registry pre-populated with the Phase 1 core indicator set at its
    conventional default periods."""
    registry = IndicatorRegistry()
    for period in (9, 20, 50, 100, 200):
        registry.register(EMAIndicator(period))
    for period in (50, 100, 200):
        registry.register(SMAIndicator(period))
    registry.register(RSIIndicator())
    registry.register(MACDIndicator())
    registry.register(BollingerBandsIndicator())
    registry.register(ATRIndicator())
    registry.register(VolumeIndicator())
    registry.register(AverageVolumeIndicator())
    registry.register(RelativeVolumeIndicator())
    registry.register(WilliamsPercentRIndicator())
    registry.register(OBVIndicator())
    registry.register(ChaikinMoneyFlowIndicator())
    return registry
