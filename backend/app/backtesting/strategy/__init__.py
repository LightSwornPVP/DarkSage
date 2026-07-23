"""Deterministic strategy interface and signal simulation for backtesting.

Strategies see only ``StrategyContext.visible_candles`` (never future data)
and emit simulation-only intents — nothing here can reach a real broker.
"""

from backend.app.backtesting.strategy.base import Strategy
from backend.app.backtesting.strategy.context import StrategyContext
from backend.app.backtesting.strategy.intent import (
    HOLD_DECISION,
    IntentAction,
    SimulatedOrderIntent,
    StrategyAction,
    StrategyDecision,
    translate_decision,
)
from backend.app.backtesting.strategy.reference import MovingAverageCrossoverStrategy
from backend.app.backtesting.strategy.simulate import simulate_signals

__all__ = [
    "HOLD_DECISION",
    "IntentAction",
    "MovingAverageCrossoverStrategy",
    "SimulatedOrderIntent",
    "Strategy",
    "StrategyAction",
    "StrategyContext",
    "StrategyDecision",
    "simulate_signals",
    "translate_decision",
]
