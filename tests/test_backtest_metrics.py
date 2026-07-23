"""Tests for backtest performance analytics against hand-computed
deterministic fixtures — explicit zero-denominator/no-trade handling, and
no silent NaN/Infinity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.backtesting.config import BacktestConfig
from backend.app.backtesting.metrics import compute_performance_metrics, compute_trade_excursion
from backend.app.backtesting.types import (
    FLAT_POSITION,
    BacktestResult,
    BacktestRun,
    EquityObservation,
    PositionState,
    SimulatedTrade,
)
from shared.models.candle import Candle, Timeframe
from shared.models.signal import SignalDirection

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
LONG_POSITION = PositionState(quantity=Decimal(1), average_entry_price=Decimal(100))


def _config(**overrides: object) -> BacktestConfig:
    fields: dict[str, object] = dict(
        strategy_id="test",
        strategy_version="1.0.0",
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=START + timedelta(days=365),
        initial_capital=Decimal(10000),
    )
    fields.update(overrides)
    return BacktestConfig(**fields)  # type: ignore[arg-type]


def _result(
    *,
    equity_values: list[str],
    trades: tuple[SimulatedTrade, ...] = (),
    positions: list[PositionState] | None = None,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    cfg = config or _config()
    positions = positions or [FLAT_POSITION] * len(equity_values)
    equity_curve = tuple(
        EquityObservation(
            timestamp=START + timedelta(days=i), equity=Decimal(value), cash=Decimal(value), position=position
        )
        for i, (value, position) in enumerate(zip(equity_values, positions, strict=True))
    )
    run = BacktestRun(config=cfg, run_id="test-run", generated_at=START)
    return BacktestResult(run=run, equity_curve=equity_curve, trades=trades, final_position=FLAT_POSITION)


def _trade(pnl: str, *, stop_price: str | None = None, entry: str = "100", quantity: str = "10") -> SimulatedTrade:
    return SimulatedTrade(
        symbol="AAPL",
        direction=SignalDirection.LONG,
        entry_time=START,
        entry_price=Decimal(entry),
        exit_time=START + timedelta(days=1),
        exit_price=Decimal(entry) + Decimal(pnl) / Decimal(quantity),
        quantity=Decimal(quantity),
        fees_paid=Decimal(0),
        pnl=Decimal(pnl),
        stop_price=Decimal(stop_price) if stop_price is not None else None,
    )


# --- No-trade / zero-denominator handling ---


def test_no_trades_leaves_trade_metrics_undefined_not_zero() -> None:
    result = _result(equity_values=["10000", "10000", "10000"])
    metrics = compute_performance_metrics(result)

    assert metrics.num_trades == 0
    assert metrics.win_rate is None
    assert metrics.profit_factor is None
    assert metrics.expectancy is None
    assert metrics.average_r_multiple is None
    assert metrics.best_trade_pnl is None
    assert metrics.worst_trade_pnl is None
    assert metrics.average_holding_time is None


def test_flat_equity_curve_has_zero_drawdown_and_zero_return() -> None:
    result = _result(equity_values=["10000", "10000", "10000"])
    metrics = compute_performance_metrics(result)

    assert metrics.total_return == Decimal(0)
    assert metrics.max_drawdown == Decimal(0)


def test_single_equity_observation_leaves_cagr_undefined() -> None:
    result = _result(equity_values=["10000"])
    metrics = compute_performance_metrics(result)
    assert metrics.cagr is None  # cannot annualize a zero-duration/single-point run


def test_zero_losses_leaves_profit_factor_undefined() -> None:
    trades = (_trade("100"), _trade("50"))
    result = _result(equity_values=["10000", "10150"], trades=trades)
    metrics = compute_performance_metrics(result)
    assert metrics.profit_factor is None  # gross_loss == 0
    assert metrics.average_loss is None
    assert metrics.win_loss_ratio is None


# --- Trade-based metrics (hand-computed) ---


def test_trade_metrics_known_values() -> None:
    trades = (
        _trade("100", stop_price="95", quantity="10"),  # win, r = 100/(5*10) = 2
        _trade("-50", stop_price="90", quantity="5"),  # loss, r = -50/(10*5) = -1
        _trade("200"),  # win, no stop -> excluded from r-multiple
        _trade("-100", stop_price="105", quantity="20"),  # loss, r = -100/(5*20) = -1
    )
    result = _result(equity_values=["10000", "10150"], trades=trades)
    metrics = compute_performance_metrics(result)

    assert metrics.num_trades == 4
    assert metrics.win_rate == Decimal("0.5")
    assert metrics.average_win == Decimal(150)  # (100+200)/2
    assert metrics.average_loss == Decimal(-75)  # (-50-100)/2
    assert metrics.win_loss_ratio == Decimal(2)  # 150/75
    assert metrics.profit_factor == Decimal(2)  # 300/150
    assert metrics.expectancy == Decimal("37.5")  # (100-50+200-100)/4
    assert metrics.best_trade_pnl == Decimal(200)
    assert metrics.worst_trade_pnl == Decimal(-100)
    assert metrics.average_r_multiple == Decimal(0)  # mean(2, -1, -1)


def test_average_holding_time_known_value() -> None:
    trade_short = _trade("10")  # entry=START, exit=START+1day (from _trade helper)
    result = _result(equity_values=["10000", "10010"], trades=(trade_short,))
    metrics = compute_performance_metrics(result)
    assert metrics.average_holding_time == timedelta(days=1)


# --- Equity-curve-based metrics (hand-computed) ---


def test_total_return_and_cagr_known_values() -> None:
    base_config = _config(end=START + timedelta(days=730))
    run = BacktestRun(config=base_config, run_id="test-run", generated_at=START)
    # Force an exact 1-year gap between the two observations for a clean CAGR.
    one_year_result = BacktestResult(
        run=run,
        equity_curve=(
            EquityObservation(timestamp=START, equity=Decimal(10000), cash=Decimal(10000), position=FLAT_POSITION),
            EquityObservation(
                timestamp=START + timedelta(days=365.25),
                equity=Decimal(12000),
                cash=Decimal(12000),
                position=FLAT_POSITION,
            ),
        ),
        trades=(),
        final_position=FLAT_POSITION,
    )
    metrics = compute_performance_metrics(one_year_result)

    assert metrics.total_return == Decimal("0.2")
    assert metrics.cagr == Decimal("0.2")  # exponent of 1 year -> CAGR == total return exactly


def test_max_drawdown_picks_the_largest_drop_across_multiple_peaks() -> None:
    result = _result(equity_values=["10000", "11000", "9900", "10890", "9801"])
    metrics = compute_performance_metrics(result)

    expected_dd = (Decimal(11000) - Decimal(9801)) / Decimal(11000)
    assert metrics.max_drawdown == expected_dd
    assert metrics.max_drawdown_duration == timedelta(days=3)  # peak at day 1, trough at day 4


def test_sharpe_is_zero_for_symmetric_zero_mean_returns() -> None:
    result = _result(equity_values=["10000", "11000", "9900", "10890", "9801"])
    metrics = compute_performance_metrics(result)
    assert metrics.sharpe_ratio == Decimal(0)


def test_sortino_undefined_when_downside_deviation_is_zero() -> None:
    # Two identical negative returns -> zero variance among downside returns.
    result = _result(equity_values=["10000", "11000", "9900", "10890", "9801"])
    metrics = compute_performance_metrics(result)
    assert metrics.sortino_ratio is None


def test_volatility_is_none_with_fewer_than_two_returns() -> None:
    result = _result(equity_values=["10000"])
    metrics = compute_performance_metrics(result)
    assert metrics.volatility is None


def test_exposure_known_value() -> None:
    positions = [FLAT_POSITION, LONG_POSITION, LONG_POSITION, FLAT_POSITION]
    result = _result(equity_values=["10000", "10010", "10020", "10020"], positions=positions)
    metrics = compute_performance_metrics(result)
    assert metrics.exposure == Decimal("0.5")


# --- Trade excursion (MAE/MFE) ---


def test_trade_excursion_known_values_long() -> None:
    trade = SimulatedTrade(
        symbol="AAPL",
        direction=SignalDirection.LONG,
        entry_time=START,
        entry_price=Decimal(100),
        exit_time=START + timedelta(days=2),
        exit_price=Decimal(105),
        quantity=Decimal(1),
        fees_paid=Decimal(0),
        pnl=Decimal(5),
    )
    candles = [
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=START,
            open=Decimal(100),
            high=Decimal(102),
            low=Decimal(95),
            close=Decimal(98),
            volume=Decimal(1000),
        ),
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=START + timedelta(days=1),
            open=Decimal(98),
            high=Decimal(110),
            low=Decimal(97),
            close=Decimal(108),
            volume=Decimal(1000),
        ),
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=START + timedelta(days=2),
            open=Decimal(108),
            high=Decimal(109),
            low=Decimal(104),
            close=Decimal(105),
            volume=Decimal(1000),
        ),
    ]

    excursion = compute_trade_excursion(trade, candles)

    assert excursion is not None
    assert excursion.mae == Decimal(5)  # entry 100 - lowest low 95
    assert excursion.mfe == Decimal(10)  # highest high 110 - entry 100


def test_trade_excursion_none_when_no_candles_in_window() -> None:
    trade = SimulatedTrade(
        symbol="AAPL",
        direction=SignalDirection.LONG,
        entry_time=START,
        entry_price=Decimal(100),
        exit_time=START,
        exit_price=Decimal(100),
        quantity=Decimal(1),
        fees_paid=Decimal(0),
        pnl=Decimal(0),
    )
    unrelated_candles = [
        Candle(
            symbol="AAPL",
            timeframe=Timeframe.D1,
            timestamp=START + timedelta(days=100),
            open=Decimal(100),
            high=Decimal(101),
            low=Decimal(99),
            close=Decimal(100),
            volume=Decimal(1000),
        )
    ]
    assert compute_trade_excursion(trade, unrelated_candles) is None
