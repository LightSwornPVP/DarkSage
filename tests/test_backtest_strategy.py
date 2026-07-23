"""Tests for the backtest strategy interface and the engine's signal ->
intent -> fill event loop: no-lookahead, determinism, warm-up, and
entry/exit sequencing."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.backtesting.config import BacktestConfig, StrategyParameterValue
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.errors import InvalidBacktestConfigError
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
from backend.app.backtesting.types import FLAT_POSITION, PositionState
from shared.models.candle import Candle, Timeframe
from shared.models.signal import SignalDirection

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


def _config_for(strategy: Strategy, end_offset: int) -> BacktestConfig:
    """A config whose strategy_id/version/parameters match ``strategy``
    exactly, since ``BacktestEngine.run_strategy`` fails closed on any
    mismatch between the strategy actually run and what the config claims."""
    return BacktestConfig(
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=START + timedelta(days=end_offset),
        initial_capital=Decimal(10000),
        parameters=strategy.parameters,
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
    spy = _RecordingStrategy()
    engine = BacktestEngine(_config_for(spy, 9), candles)

    engine.run_strategy(spy)

    assert len(spy.seen_visible_candles) == 10
    for call_index, visible in enumerate(spy.seen_visible_candles):
        assert visible == tuple(candles[: call_index + 1])
        future_timestamps = {c.timestamp for c in candles[call_index + 1 :]}
        seen_timestamps = {c.timestamp for c in visible}
        assert seen_timestamps.isdisjoint(future_timestamps)


# --- Warm-up behavior ---


def test_strategy_produces_no_decisions_before_warmup() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(5)]

    class _WarmupSpy(_RecordingStrategy):
        @property
        def warmup_period(self) -> int:
            return 4

    warmup_spy = _WarmupSpy()
    engine = BacktestEngine(_config_for(warmup_spy, 4), candles)
    engine.run_strategy(warmup_spy)
    # Only bars with >= 4 visible candles reach decide(): indices 3, 4 (2 calls).
    assert len(warmup_spy.seen_visible_candles) == 2
    assert len(warmup_spy.seen_visible_candles[0]) == 4


def test_reference_strategy_holds_during_warmup() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(5)]
    strategy = MovingAverageCrossoverStrategy(fast_period=3, slow_period=20)
    engine = BacktestEngine(_config_for(strategy, 4), candles)
    result = engine.run_strategy(strategy)
    assert result.trades == ()  # never reaches slow_period + 1 = 21 visible candles


# --- Event-loop ordering: no future fills, no phantom state from unfilled intents ---


class _ScriptedStrategy(Strategy):
    """Strategy that deterministically follows a bar-index -> decision
    script, for pinning exact event-loop ordering behavior."""

    def __init__(self, script: Mapping[int, StrategyDecision]) -> None:
        self._script = script

    @property
    def strategy_id(self) -> str:
        return "scripted"

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
        bar_index = len(context.visible_candles) - 1
        return self._script.get(bar_index, HOLD_DECISION)


def test_engine_fill_never_appears_before_the_bar_it_actually_resolved_on() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(6)]  # indices 0..5
    strategy = _ScriptedStrategy({2: StrategyDecision(action=StrategyAction.ENTER_LONG)})
    engine = BacktestEngine(_config_for(strategy, 5), candles)

    result = engine.run_strategy(strategy)

    # Signal fires at bar index 2 (visible_candles length 3). NEXT_BAR_OPEN
    # means the earliest legal fill is bar index 3 -- so bars 0-2 must show
    # a flat position, never the fill that hasn't happened yet.
    for observation in result.equity_curve[:3]:
        assert observation.position.is_flat
    assert not result.equity_curve[3].position.is_flat
    assert len(result.trades) == 0  # never exited: still open at end of data


def test_engine_signal_on_final_bar_never_fills_and_leaves_state_untouched() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(4)]  # indices 0..3, last index=3
    strategy = _ScriptedStrategy({3: StrategyDecision(action=StrategyAction.ENTER_LONG)})
    engine = BacktestEngine(_config_for(strategy, 3), candles)

    result = engine.run_strategy(strategy)

    # A signal on the very last bar has no bar N+1 to fill against under
    # NEXT_BAR_OPEN -- it must be discarded, not retried and not applied.
    assert result.trades == ()
    assert result.final_position.is_flat
    assert all(observation.position.is_flat for observation in result.equity_curve)


# --- Parameter lineage identity: type-preserving strategy/config matching ---


class _ParamStrategy(_RecordingStrategy):
    """A recording strategy with a configurable single parameter, for
    exercising strategy/config parameter-lineage matching."""

    def __init__(self, value: StrategyParameterValue) -> None:
        super().__init__()
        self._value = value

    @property
    def strategy_id(self) -> str:
        return "param-strategy"

    @property
    def parameters(self) -> Mapping[str, StrategyParameterValue]:
        return {"p": self._value}


def _config_with_parameter(strategy: Strategy, value: StrategyParameterValue) -> BacktestConfig:
    return BacktestConfig(
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=START + timedelta(days=2),
        initial_capital=Decimal(10000),
        parameters={"p": value},
    )


def test_run_strategy_rejects_bool_vs_int_parameter_mismatch() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(3)]
    strategy = _ParamStrategy(True)
    config = _config_with_parameter(strategy, 1)  # int 1, not bool True
    with pytest.raises(InvalidBacktestConfigError):
        BacktestEngine(config, candles).run_strategy(strategy)


def test_run_strategy_rejects_decimal_vs_int_parameter_mismatch() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(3)]
    strategy = _ParamStrategy(Decimal("1"))
    config = _config_with_parameter(strategy, 1)  # int 1, not Decimal("1")
    with pytest.raises(InvalidBacktestConfigError):
        BacktestEngine(config, candles).run_strategy(strategy)


def test_run_strategy_accepts_matching_typed_parameter() -> None:
    candles = [_candle(i, str(100 + i)) for i in range(3)]
    strategy = _ParamStrategy(Decimal("1"))
    config = _config_with_parameter(strategy, Decimal("1"))
    result = BacktestEngine(config, candles).run_strategy(strategy)  # must not raise
    assert result.final_position.is_flat


# --- Determinism ---


def test_reference_strategy_signals_are_deterministic() -> None:
    candles = [_candle(i, price) for i, price in enumerate(_crossover_prices())]
    strategy_a = MovingAverageCrossoverStrategy(fast_period=3, slow_period=5)
    strategy_b = MovingAverageCrossoverStrategy(fast_period=3, slow_period=5)
    config = _config_for(strategy_a, len(candles) - 1)

    result_a = BacktestEngine(config, candles).run_strategy(strategy_a)
    result_b = BacktestEngine(config, candles).run_strategy(strategy_b)

    assert result_a.trades == result_b.trades
    assert len(result_a.trades) > 0  # the crossover pattern must actually produce trades


# --- Entry/exit sequencing ---


def test_reference_strategy_produces_non_overlapping_long_trades() -> None:
    candles = [_candle(i, price) for i, price in enumerate(_crossover_prices())]
    strategy = MovingAverageCrossoverStrategy(fast_period=3, slow_period=5)
    config = _config_for(strategy, len(candles) - 1)

    result = BacktestEngine(config, candles).run_strategy(strategy)

    assert len(result.trades) >= 1
    # Every completed trade is a full long round-trip that closed before the
    # next one opened. ``Portfolio`` enforces this at runtime (it raises if
    # asked to open while already open, or close while flat) — this is a
    # regression check on that guarantee, not a new one.
    for trade in result.trades:
        assert trade.direction is SignalDirection.LONG
        assert trade.entry_time < trade.exit_time
    for previous, current in zip(result.trades, result.trades[1:], strict=False):
        assert previous.exit_time <= current.entry_time


def test_reference_strategy_rejects_fast_not_less_than_slow() -> None:
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(fast_period=10, slow_period=10)


def test_reference_strategy_identity_and_parameters() -> None:
    strategy = MovingAverageCrossoverStrategy(fast_period=3, slow_period=5, version="9.9.9")
    assert strategy.strategy_id == "reference-ma-crossover"
    assert strategy.strategy_version == "9.9.9"
    assert strategy.parameters == {"fast_period": 3, "slow_period": 5}
    assert strategy.warmup_period == 6
