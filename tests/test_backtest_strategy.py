"""Tests for the backtest strategy interface and signal simulation:
no-lookahead, determinism, warm-up, and entry/exit sequencing."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.backtesting.config import BacktestConfig, StrategyParameterValue
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.strategy.base import Strategy
from backend.app.backtesting.strategy.context import StrategyContext
from backend.app.backtesting.strategy.intent import (
    HOLD_DECISION,
    IntentAction,
    StrategyAction,
    StrategyDecision,
    translate_decision,
)
from backend.app.backtesting.strategy.reference import MovingAverageCrossoverStrategy
from backend.app.backtesting.strategy.simulate import simulate_signals
from backend.app.backtesting.types import FLAT_POSITION, PositionState
from shared.models.candle import Candle, Timeframe

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(day_offset: int, close: str) -> Candle:
    price = Decimal(close)
    return Candle(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=START + timedelta(days=day_offset),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=Decimal(1000),
    )


def _config(end_offset: int) -> BacktestConfig:
    return BacktestConfig(
        strategy_id="test",
        strategy_version="1.0.0",
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=START + timedelta(days=end_offset),
        initial_capital=Decimal(10000),
    )


def _crossover_prices() -> list[str]:
    # Flat, then up, then down. Verified (by direct SMA(3)/SMA(5) computation
    # over this exact sequence) to produce exactly one crossover above at
    # index 8 and one crossover below at index 25 — the flat lead-in matters:
    # a sequence that starts already monotonic never shows a "prior state
    # where fast <= slow" to cross away from.
    flat = [100] * 8
    up = list(range(101, 116))
    down = list(range(114, 89, -1))
    return [str(p) for p in flat + up + down]


# --- translate_decision: no duplicate impossible transitions ---


def test_translate_decision_hold_produces_no_intent() -> None:
    assert translate_decision(HOLD_DECISION, FLAT_POSITION, START, 0) is None


def test_translate_decision_enter_long_while_flat_produces_intent() -> None:
    intent = translate_decision(
        StrategyDecision(action=StrategyAction.ENTER_LONG), FLAT_POSITION, START, 0
    )
    assert intent is not None
    assert intent.action is IntentAction.OPEN_LONG
    assert intent.signal_index == 0


def test_translate_decision_enter_long_while_already_long_is_noop() -> None:
    long_position = PositionState(quantity=Decimal(1), average_entry_price=Decimal(100))
    assert translate_decision(StrategyDecision(action=StrategyAction.ENTER_LONG), long_position, START, 0) is None


def test_translate_decision_exit_while_flat_is_noop() -> None:
    assert translate_decision(StrategyDecision(action=StrategyAction.EXIT), FLAT_POSITION, START, 0) is None


def test_translate_decision_exit_while_long_produces_close_intent() -> None:
    long_position = PositionState(quantity=Decimal(1), average_entry_price=Decimal(100))
    intent = translate_decision(StrategyDecision(action=StrategyAction.EXIT), long_position, START, 0)
    assert intent is not None
    assert intent.action is IntentAction.CLOSE


def test_translate_decision_enter_short_while_long_is_noop() -> None:
    long_position = PositionState(quantity=Decimal(1), average_entry_price=Decimal(100))
    assert translate_decision(StrategyDecision(action=StrategyAction.ENTER_SHORT), long_position, START, 0) is None


def test_strategy_decision_rejects_non_positive_stop() -> None:
    with pytest.raises(ValueError):
        StrategyDecision(action=StrategyAction.ENTER_LONG, stop_price=Decimal(0))


# --- No lookahead ---


class _RecordingStrategy(Strategy):
    """Spy strategy: records exactly what it was shown at each call."""

    def __init__(self) -> None:
        self.seen_visible_candles: list[tuple[Candle, ...]] = []

    @property
    def strategy_id(self) -> str:
        return "recording-spy"

    @property
    def strategy_version(self) -> str:
        return "1.0.0"

    @property
    def parameters(self) -> Mapping[str, StrategyParameterValue]:
        return {}

    @property
    def warmup_period(self) -> int:
        return 1

    def decide(self, context: StrategyContext) -> StrategyDecision:
        self.seen_visible_candles.append(context.visible_candles)
        return HOLD_DECISION


def test_strategy_never_sees_future_candles() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(10)]
    engine = BacktestEngine(_config(9), candles)
    spy = _RecordingStrategy()

    simulate_signals(engine.iter_steps(), spy)

    assert len(spy.seen_visible_candles) == 10
    for call_index, visible in enumerate(spy.seen_visible_candles):
        assert visible == tuple(candles[: call_index + 1])
        future_timestamps = {c.timestamp for c in candles[call_index + 1 :]}
        seen_timestamps = {c.timestamp for c in visible}
        assert seen_timestamps.isdisjoint(future_timestamps)


# --- Warm-up behavior ---


def test_strategy_produces_no_decisions_before_warmup() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(5)]
    engine = BacktestEngine(_config(4), candles)

    class _WarmupSpy(_RecordingStrategy):
        @property
        def warmup_period(self) -> int:
            return 4

    warmup_spy = _WarmupSpy()
    simulate_signals(engine.iter_steps(), warmup_spy)
    # Only bars with >= 4 visible candles reach decide(): indices 3, 4 (2 calls).
    assert len(warmup_spy.seen_visible_candles) == 2
    assert len(warmup_spy.seen_visible_candles[0]) == 4


def test_reference_strategy_holds_during_warmup() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(5)]
    strategy = MovingAverageCrossoverStrategy(fast_period=3, slow_period=20)
    engine = BacktestEngine(_config(4), candles)
    intents = simulate_signals(engine.iter_steps(), strategy)
    assert intents == ()  # never reaches slow_period + 1 = 21 visible candles


# --- Determinism ---


def test_reference_strategy_signals_are_deterministic() -> None:
    candles = [_candle(i, price) for i, price in enumerate(_crossover_prices())]
    config = _config(len(candles) - 1)

    strategy_a = MovingAverageCrossoverStrategy(fast_period=3, slow_period=5)
    strategy_b = MovingAverageCrossoverStrategy(fast_period=3, slow_period=5)

    intents_a = simulate_signals(BacktestEngine(config, candles).iter_steps(), strategy_a)
    intents_b = simulate_signals(BacktestEngine(config, candles).iter_steps(), strategy_b)

    assert intents_a == intents_b
    assert len(intents_a) > 0  # the crossover pattern must actually produce signals


# --- Entry/exit sequencing ---


def test_reference_strategy_alternates_open_and_close_without_duplicates() -> None:
    candles = [_candle(i, price) for i, price in enumerate(_crossover_prices())]
    config = _config(len(candles) - 1)
    strategy = MovingAverageCrossoverStrategy(fast_period=3, slow_period=5)

    intents = simulate_signals(BacktestEngine(config, candles).iter_steps(), strategy)

    assert len(intents) >= 2  # at least one open + one close given the up-then-down pattern
    # Must strictly alternate OPEN_LONG, CLOSE, OPEN_LONG, CLOSE, ... — never
    # two opens or two closes in a row (that would be an impossible transition).
    for previous, current in zip(intents, intents[1:], strict=False):
        assert previous.action != current.action
    assert intents[0].action is IntentAction.OPEN_LONG


def test_reference_strategy_rejects_fast_not_less_than_slow() -> None:
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(fast_period=10, slow_period=10)


def test_reference_strategy_identity_and_parameters() -> None:
    strategy = MovingAverageCrossoverStrategy(fast_period=3, slow_period=5, version="9.9.9")
    assert strategy.strategy_id == "reference-ma-crossover"
    assert strategy.strategy_version == "9.9.9"
    assert strategy.parameters == {"fast_period": 3, "slow_period": 5}
    assert strategy.warmup_period == 6
