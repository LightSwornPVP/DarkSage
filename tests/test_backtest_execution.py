"""Tests for simulated execution/cost simulation and portfolio bookkeeping:
fees, slippage, fill-timing rules, gap behavior, liquidity caps, and
determinism."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.backtesting.config import CostConfig, ExecutionConfig, FillTiming, PositionSizingConfig
from backend.app.backtesting.errors import InvalidExecutionConfigError
from backend.app.backtesting.execution.fill import SimulatedFill
from backend.app.backtesting.execution.simulator import ExecutionSimulator
from backend.app.backtesting.portfolio import Portfolio
from backend.app.backtesting.strategy.intent import IntentAction, SimulatedOrderIntent
from backend.app.backtesting.types import FLAT_POSITION, PositionState
from shared.models.candle import Candle, Timeframe
from shared.models.signal import SignalDirection

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _candle(day_offset: int, *, open: str, close: str, volume: str = "1000") -> Candle:
    open_price = Decimal(open)
    close_price = Decimal(close)
    high = max(open_price, close_price) + 1
    low = min(open_price, close_price) - 1
    return Candle(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        timestamp=START + timedelta(days=day_offset),
        open=open_price,
        high=high,
        low=low,
        close=close_price,
        volume=Decimal(volume),
    )


def _intent(action: IntentAction, signal_index: int = 0) -> SimulatedOrderIntent:
    return SimulatedOrderIntent(
        action=action, signal_time=START + timedelta(days=signal_index), signal_index=signal_index
    )


# --- Commission ---


def test_commission_applied_correctly() -> None:
    config = ExecutionConfig(cost=CostConfig(commission_rate=Decimal("0.01")))
    simulator = ExecutionSimulator(config)
    candles = [_candle(0, open="100", close="100"), _candle(1, open="110", close="112")]

    fill = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG),
        candles=candles,
        position=FLAT_POSITION,
        equity_at_signal=Decimal(1100),
    )

    assert fill is not None
    assert fill.fill_price == Decimal(110)
    assert fill.quantity == Decimal(10)
    assert fill.commission == Decimal("11.0")  # 110 * 10 * 0.01


# --- Slippage / spread ---


def test_slippage_and_spread_applied_on_buy() -> None:
    config = ExecutionConfig(cost=CostConfig(spread=Decimal(1), slippage_rate=Decimal("0.01")))
    simulator = ExecutionSimulator(ExecutionConfig(cost=config.cost, fill_timing=FillTiming.SAME_BAR_CLOSE))
    candles = [_candle(0, open="100", close="100")]

    fill = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG), candles=candles, position=FLAT_POSITION, equity_at_signal=Decimal(1000)
    )

    assert fill is not None
    # base=100, adjustment = spread/2 (0.5) + 100*0.01 (1.0) = 1.5 -> buy pays more
    assert fill.fill_price == Decimal("101.5")


def test_slippage_and_spread_applied_on_sell() -> None:
    config = ExecutionConfig(
        cost=CostConfig(spread=Decimal(1), slippage_rate=Decimal("0.01")), fill_timing=FillTiming.SAME_BAR_CLOSE
    )
    simulator = ExecutionSimulator(config)
    long_position = PositionState(quantity=Decimal(10), average_entry_price=Decimal(90))
    candles = [_candle(0, open="100", close="100")]

    fill = simulator.fill_intent(
        _intent(IntentAction.CLOSE), candles=candles, position=long_position, equity_at_signal=Decimal(1000)
    )

    assert fill is not None
    assert fill.fill_price == Decimal("98.5")  # sell receives less: 100 - 1.5


# --- Fill timing / no lookahead / gap behavior ---


def test_same_bar_close_uses_only_the_signal_bar() -> None:
    config = ExecutionConfig(fill_timing=FillTiming.SAME_BAR_CLOSE)
    simulator = ExecutionSimulator(config)
    candles = [_candle(0, open="100", close="100"), _candle(1, open="999", close="999")]

    fill = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG, signal_index=0),
        candles=candles,
        position=FLAT_POSITION,
        equity_at_signal=Decimal(100),
    )

    assert fill is not None
    assert fill.fill_price == Decimal(100)  # never touches candle[1]'s 999


def test_next_bar_open_uses_the_following_bar_not_the_signal_bar() -> None:
    simulator = ExecutionSimulator(ExecutionConfig())  # NEXT_BAR_OPEN is the default
    candles = [_candle(0, open="90", close="100"), _candle(1, open="105", close="107")]

    fill = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG, signal_index=0),
        candles=candles,
        position=FLAT_POSITION,
        equity_at_signal=Decimal(105),
    )

    assert fill is not None
    assert fill.fill_price == Decimal(105)  # candle[1].open, not candle[0].close (100)


def test_next_bar_open_returns_none_at_end_of_history() -> None:
    simulator = ExecutionSimulator(ExecutionConfig())
    candles = [_candle(0, open="100", close="100")]

    fill = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG, signal_index=0),
        candles=candles,
        position=FLAT_POSITION,
        equity_at_signal=Decimal(100),
    )

    assert fill is None  # no bar 1 exists — fail-safe, not a fabricated fill


def test_gap_behavior_uses_the_real_gapped_open() -> None:
    simulator = ExecutionSimulator(ExecutionConfig())
    candles = [_candle(0, open="90", close="100"), _candle(1, open="150", close="151")]  # big gap up

    fill = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG, signal_index=0),
        candles=candles,
        position=FLAT_POSITION,
        equity_at_signal=Decimal(150),
    )

    assert fill is not None
    assert fill.fill_price == Decimal(150)  # the real gapped price, not interpolated from the prior close


# --- Determinism ---


def test_fill_intent_is_deterministic() -> None:
    simulator = ExecutionSimulator(ExecutionConfig(cost=CostConfig(commission_rate=Decimal("0.001"))))
    candles = [_candle(0, open="100", close="100"), _candle(1, open="101", close="102")]

    fill_a = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG), candles=candles, position=FLAT_POSITION, equity_at_signal=Decimal(1000)
    )
    fill_b = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG), candles=candles, position=FLAT_POSITION, equity_at_signal=Decimal(1000)
    )

    assert fill_a == fill_b


# --- Liquidity constraint ---


def test_max_participation_rate_caps_entry_quantity() -> None:
    config = ExecutionConfig(
        fill_timing=FillTiming.SAME_BAR_CLOSE,
        position_sizing=PositionSizingConfig(max_participation_rate=Decimal("0.1")),
    )
    simulator = ExecutionSimulator(config)
    candles = [_candle(0, open="100", close="100", volume="100")]  # cap = 100 * 0.1 = 10

    fill = simulator.fill_intent(
        _intent(IntentAction.OPEN_LONG),
        candles=candles,
        position=FLAT_POSITION,
        equity_at_signal=Decimal(1_000_000),  # would otherwise size to 10,000 shares
    )

    assert fill is not None
    assert fill.quantity == Decimal(10)


# --- Invalid configuration / invalid transitions fail closed ---


def test_extreme_spread_producing_non_positive_price_raises() -> None:
    config = ExecutionConfig(cost=CostConfig(spread=Decimal(1000)), fill_timing=FillTiming.SAME_BAR_CLOSE)
    simulator = ExecutionSimulator(config)
    long_position = PositionState(quantity=Decimal(1), average_entry_price=Decimal(100))
    candles = [_candle(0, open="100", close="100")]

    with pytest.raises(InvalidExecutionConfigError):
        simulator.fill_intent(
            _intent(IntentAction.CLOSE), candles=candles, position=long_position, equity_at_signal=Decimal(100)
        )


def test_close_against_flat_position_raises() -> None:
    simulator = ExecutionSimulator(ExecutionConfig(fill_timing=FillTiming.SAME_BAR_CLOSE))
    candles = [_candle(0, open="100", close="100")]
    with pytest.raises(InvalidExecutionConfigError):
        simulator.fill_intent(
            _intent(IntentAction.CLOSE), candles=candles, position=FLAT_POSITION, equity_at_signal=Decimal(100)
        )


def test_position_sizing_rejects_invalid_equity_fraction() -> None:
    with pytest.raises(InvalidExecutionConfigError):
        PositionSizingConfig(equity_fraction=Decimal("1.5"))


def test_simulated_fill_rejects_fill_before_signal() -> None:
    with pytest.raises(ValueError):
        SimulatedFill(
            action=IntentAction.OPEN_LONG,
            signal_time=START + timedelta(days=1),
            fill_time=START,  # before the signal — impossible
            fill_price=Decimal(100),
            quantity=Decimal(1),
            commission=Decimal(0),
        )


def test_simulated_fill_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValueError):
        SimulatedFill(
            action=IntentAction.OPEN_LONG,
            signal_time=START,
            fill_time=START,
            fill_price=Decimal(100),
            quantity=Decimal(0),
            commission=Decimal(0),
        )


# --- Portfolio bookkeeping ---


def _fill(action: IntentAction, *, price: str, quantity: str, commission: str, day: int = 0) -> SimulatedFill:
    return SimulatedFill(
        action=action,
        signal_time=START + timedelta(days=day),
        fill_time=START + timedelta(days=day),
        fill_price=Decimal(price),
        quantity=Decimal(quantity),
        commission=Decimal(commission),
    )


def test_portfolio_open_long_updates_cash_and_position() -> None:
    portfolio = Portfolio(initial_capital=Decimal(10000), symbol="AAPL")
    portfolio.apply_fill(_fill(IntentAction.OPEN_LONG, price="100", quantity="10", commission="5"))

    assert portfolio.cash == Decimal(10000) - Decimal(1000) - Decimal(5)
    assert portfolio.position.quantity == Decimal(10)
    assert portfolio.position.direction is SignalDirection.LONG


def test_portfolio_close_long_records_trade_with_correct_pnl() -> None:
    portfolio = Portfolio(initial_capital=Decimal(10000), symbol="AAPL")
    portfolio.apply_fill(_fill(IntentAction.OPEN_LONG, price="100", quantity="10", commission="5", day=0))
    portfolio.apply_fill(_fill(IntentAction.CLOSE, price="120", quantity="10", commission="6", day=1))

    assert portfolio.position.is_flat
    assert portfolio.cash == Decimal(10189)  # 10000 - 1000 - 5 + 1200 - 6
    assert len(portfolio.trades) == 1
    trade = portfolio.trades[0]
    assert trade.direction is SignalDirection.LONG
    assert trade.fees_paid == Decimal(11)
    assert trade.pnl == Decimal(189)


def test_portfolio_short_round_trip_pnl() -> None:
    portfolio = Portfolio(initial_capital=Decimal(10000), symbol="AAPL")
    portfolio.apply_fill(_fill(IntentAction.OPEN_SHORT, price="100", quantity="10", commission="5", day=0))
    portfolio.apply_fill(_fill(IntentAction.CLOSE, price="90", quantity="10", commission="6", day=1))

    assert portfolio.cash == Decimal(10089)  # 10000 + 1000 - 5 - 900 - 6
    trade = portfolio.trades[0]
    assert trade.direction is SignalDirection.SHORT
    assert trade.pnl == Decimal(89)  # (100-90)*10 - 11 fees


def test_portfolio_equity_reflects_open_position_market_value() -> None:
    portfolio = Portfolio(initial_capital=Decimal(10000), symbol="AAPL")
    portfolio.apply_fill(_fill(IntentAction.OPEN_LONG, price="100", quantity="10", commission="0"))
    assert portfolio.equity(Decimal(110)) == Decimal(10100)  # 9000 cash + 10*110


def test_portfolio_close_while_flat_raises() -> None:
    portfolio = Portfolio(initial_capital=Decimal(10000), symbol="AAPL")
    with pytest.raises(ValueError):
        portfolio.apply_fill(_fill(IntentAction.CLOSE, price="100", quantity="10", commission="0"))


def test_portfolio_open_while_already_open_raises() -> None:
    portfolio = Portfolio(initial_capital=Decimal(10000), symbol="AAPL")
    portfolio.apply_fill(_fill(IntentAction.OPEN_LONG, price="100", quantity="10", commission="0"))
    with pytest.raises(ValueError):
        portfolio.apply_fill(_fill(IntentAction.OPEN_LONG, price="100", quantity="10", commission="0"))


# --- End-to-end: BacktestEngine.run_strategy wires strategy + execution + portfolio ---


def test_run_strategy_produces_trades_and_is_deterministic() -> None:
    from backend.app.backtesting.config import BacktestConfig
    from backend.app.backtesting.engine import BacktestEngine
    from backend.app.backtesting.strategy.reference import MovingAverageCrossoverStrategy

    flat = [100] * 8
    up = list(range(101, 116))
    down = list(range(114, 89, -1))
    closes = [str(p) for p in flat + up + down]
    candles = [_candle(i, open=c, close=c) for i, c in enumerate(closes)]

    config = BacktestConfig(
        strategy_id="reference-ma-crossover",
        strategy_version="1.0.0",
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=START + timedelta(days=len(candles)),
        initial_capital=Decimal(10000),
        execution_config=ExecutionConfig(fill_timing=FillTiming.SAME_BAR_CLOSE),
    )

    def fixed_clock() -> datetime:
        return datetime(2026, 6, 1, tzinfo=timezone.utc)

    result_a = BacktestEngine(config, candles, clock=fixed_clock).run_strategy(
        MovingAverageCrossoverStrategy(fast_period=3, slow_period=5)
    )
    result_b = BacktestEngine(config, candles, clock=fixed_clock).run_strategy(
        MovingAverageCrossoverStrategy(fast_period=3, slow_period=5)
    )

    assert result_a == result_b
    assert len(result_a.trades) >= 1
    assert len(result_a.equity_curve) > 0
    # No lookahead sanity check: every trade's entry/exit timestamps must be
    # real candle timestamps that actually appear in the supplied history.
    candle_timestamps = {c.timestamp for c in candles}
    for trade in result_a.trades:
        assert trade.entry_time in candle_timestamps
        assert trade.exit_time in candle_timestamps
