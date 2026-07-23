"""``MovingAverageCrossoverStrategy`` — a reference strategy for exercising
the backtesting infrastructure end-to-end.

This exists ONLY to validate that the Strategy interface, signal
simulation, and (from Slice 2.3 onward) execution/metrics pipeline work
correctly. It is intentionally simple, is not tuned, and is not a claim
that moving-average crossover is profitable or production-approved — see
PROJECT_SPEC.md Section 6 for the real strategy-family requirements.
"""

from __future__ import annotations

from collections.abc import Mapping

from backend.app.backtesting.config import StrategyParameterValue
from backend.app.backtesting.strategy.base import Strategy
from backend.app.backtesting.strategy.context import StrategyContext
from backend.app.backtesting.strategy.intent import HOLD_DECISION, StrategyAction, StrategyDecision
from backend.app.indicators.library.moving_average import SMAIndicator
from shared.models.signal import SignalDirection


class MovingAverageCrossoverStrategy(Strategy):
    """Long-only: enters when the fast SMA crosses above the slow SMA,
    exits when it crosses back below. No short capability — kept simple
    since this is a test/reference fixture, not a product strategy."""

    def __init__(self, fast_period: int = 10, slow_period: int = 20, *, version: str = "1.0.0") -> None:
        if fast_period < 1 or slow_period < 1:
            raise ValueError("fast_period and slow_period must be >= 1")
        if fast_period >= slow_period:
            raise ValueError("fast_period must be < slow_period")
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._fast_indicator = SMAIndicator(fast_period)
        self._slow_indicator = SMAIndicator(slow_period)
        self._version = version

    @property
    def strategy_id(self) -> str:
        return "reference-ma-crossover"

    @property
    def strategy_version(self) -> str:
        return self._version

    @property
    def parameters(self) -> Mapping[str, StrategyParameterValue]:
        return {"fast_period": self._fast_period, "slow_period": self._slow_period}

    @property
    def warmup_period(self) -> int:
        # +1 beyond the slow SMA's own warm-up so a *prior* SMA pair exists
        # to detect a cross (a single pair alone can't show a transition).
        return self._slow_period + 1

    def decide(self, context: StrategyContext) -> StrategyDecision:
        candles = context.visible_candles
        fast_result = self._fast_indicator.compute(candles)
        slow_result = self._slow_indicator.compute(candles)
        if len(fast_result.points) < 2 or len(slow_result.points) < 2:
            return HOLD_DECISION

        fast_now = fast_result.points[-1].values["sma"]
        fast_prev = fast_result.points[-2].values["sma"]
        slow_now = slow_result.points[-1].values["sma"]
        slow_prev = slow_result.points[-2].values["sma"]

        crossed_above = fast_prev <= slow_prev and fast_now > slow_now
        crossed_below = fast_prev >= slow_prev and fast_now < slow_now

        if crossed_above and context.position.is_flat:
            return StrategyDecision(action=StrategyAction.ENTER_LONG, reason="fast SMA crossed above slow SMA")
        if crossed_below and context.position.direction is SignalDirection.LONG:
            return StrategyDecision(action=StrategyAction.EXIT, reason="fast SMA crossed below slow SMA")
        return HOLD_DECISION
