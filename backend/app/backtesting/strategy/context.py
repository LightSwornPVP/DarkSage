"""``StrategyContext`` — exactly what a strategy is allowed to see.

Constructed once per active bar from ``BacktestStep.visible_candles``,
which is already sliced to exclude every future candle — a strategy has no
API surface through which it could reach beyond ``visible_candles``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.app.backtesting.config import StrategyParameterValue
from backend.app.backtesting.types import PositionState
from shared.models.candle import Candle


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Read-only view of "the world as of now" for one strategy decision."""

    visible_candles: tuple[Candle, ...]
    position: PositionState
    parameters: Mapping[str, StrategyParameterValue]

    def __post_init__(self) -> None:
        if not self.visible_candles:
            raise ValueError("StrategyContext requires at least one visible candle")

    @property
    def current_candle(self) -> Candle:
        return self.visible_candles[-1]
