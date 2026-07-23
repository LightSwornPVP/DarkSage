"""``simulate_signals`` — runs a ``Strategy`` over a backtest's chronological
steps and produces the resulting sequence of simulated order intents.

This is signal/intent generation only — no prices are filled and no costs
are applied here (that is Slice 2.3). A lightweight placeholder position
(quantity=1, at an arbitrary positive placeholder entry price) is tracked
purely so consecutive decisions reconcile correctly against "am I currently
long/short/flat" — the real quantity/entry price come from execution.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from backend.app.backtesting.history import BacktestStep
from backend.app.backtesting.strategy.base import Strategy
from backend.app.backtesting.strategy.context import StrategyContext
from backend.app.backtesting.strategy.intent import IntentAction, SimulatedOrderIntent, translate_decision
from backend.app.backtesting.types import FLAT_POSITION, PositionState

_PLACEHOLDER_PRICE = Decimal(1)


def _tentative_position_after(intent: SimulatedOrderIntent, position: PositionState) -> PositionState:
    if intent.action is IntentAction.OPEN_LONG:
        return PositionState(quantity=Decimal(1), average_entry_price=_PLACEHOLDER_PRICE)
    if intent.action is IntentAction.OPEN_SHORT:
        return PositionState(quantity=Decimal(-1), average_entry_price=_PLACEHOLDER_PRICE)
    if intent.action is IntentAction.CLOSE:
        return FLAT_POSITION
    raise AssertionError(f"unhandled IntentAction: {intent.action}")


def simulate_signals(steps: Iterable[BacktestStep], strategy: Strategy) -> tuple[SimulatedOrderIntent, ...]:
    """Run ``strategy`` over ``steps`` (from ``BacktestEngine.iter_steps()``),
    returning the intents it produced, in chronological order.

    Inactive (pre-``start`` warm-up) bars and bars with fewer visible
    candles than ``strategy.warmup_period`` never reach ``strategy.decide``.
    """
    intents: list[SimulatedOrderIntent] = []
    position = FLAT_POSITION

    for step in steps:
        if not step.is_active:
            continue
        if len(step.visible_candles) < strategy.warmup_period:
            continue

        context = StrategyContext(
            visible_candles=step.visible_candles, position=position, parameters=strategy.parameters
        )
        decision = strategy.decide(context)
        intent = translate_decision(decision, position, step.candle.timestamp, step.index)
        if intent is None:
            continue

        intents.append(intent)
        position = _tentative_position_after(intent, position)

    return tuple(intents)
