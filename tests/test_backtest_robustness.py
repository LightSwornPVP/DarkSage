"""Tests for Monte Carlo resampling and parameter-stability analysis:
determinism given a seed, insufficient-sample rejection, and exact
known-value checks using degenerate (all-identical-outcome) trade sets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.backtesting.config import BacktestConfig
from backend.app.backtesting.errors import InsufficientSampleSizeError
from backend.app.backtesting.metrics import compute_performance_metrics
from backend.app.backtesting.robustness import (
    MonteCarloConfig,
    ParameterStabilityPoint,
    ParameterStabilityResult,
    assess_stability,
    run_monte_carlo,
    run_parameter_stability,
)
from backend.app.backtesting.types import (
    FLAT_POSITION,
    BacktestResult,
    BacktestRun,
    EquityObservation,
    SimulatedTrade,
)
from shared.models.candle import Timeframe
from shared.models.signal import SignalDirection

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _trade(pnl: str, day: int) -> SimulatedTrade:
    return SimulatedTrade(
        symbol="AAPL",
        direction=SignalDirection.LONG,
        entry_time=START + timedelta(days=day),
        entry_price=Decimal(100),
        exit_time=START + timedelta(days=day + 1),
        exit_price=Decimal(100) + Decimal(pnl),
        quantity=Decimal(1),
        fees_paid=Decimal(0),
        pnl=Decimal(pnl),
    )


# --- Insufficient sample size ---


def test_run_monte_carlo_rejects_insufficient_trades() -> None:
    trades = tuple(_trade("10", i) for i in range(5))
    with pytest.raises(InsufficientSampleSizeError):
        run_monte_carlo(trades, initial_capital=Decimal(10000), config=MonteCarloConfig(min_trades_required=20))


# --- Determinism ---


def test_run_monte_carlo_is_deterministic_with_same_seed() -> None:
    trades = tuple(_trade("10" if i % 2 == 0 else "-5", i) for i in range(25))
    config = MonteCarloConfig(num_simulations=200, random_seed=42, min_trades_required=20)

    result_a = run_monte_carlo(trades, initial_capital=Decimal(10000), config=config)
    result_b = run_monte_carlo(trades, initial_capital=Decimal(10000), config=config)

    assert result_a == result_b


def test_run_monte_carlo_bootstrap_is_deterministic_with_same_seed() -> None:
    trades = tuple(_trade("10" if i % 2 == 0 else "-5", i) for i in range(25))
    config = MonteCarloConfig(num_simulations=200, random_seed=7, min_trades_required=20, method="bootstrap")

    result_a = run_monte_carlo(trades, initial_capital=Decimal(10000), config=config)
    result_b = run_monte_carlo(trades, initial_capital=Decimal(10000), config=config)

    assert result_a == result_b


# --- Exact known values via a degenerate (all-identical-outcome) trade set ---


def test_reshuffle_with_identical_trade_outcomes_has_zero_drawdown_and_fixed_ending_equity() -> None:
    # Every trade wins +10: any permutation sums to the same total and is
    # monotonically increasing, so every simulated path has zero drawdown
    # and the exact same ending equity.
    trades = tuple(_trade("10", i) for i in range(25))
    config = MonteCarloConfig(num_simulations=100, random_seed=1, min_trades_required=20)

    result = run_monte_carlo(trades, initial_capital=Decimal(10000), config=config)

    expected_ending_equity = Decimal(10000) + Decimal(250)
    assert all(value == expected_ending_equity for value in result.ending_equity_percentiles.values())
    assert all(value == Decimal(0) for value in result.max_drawdown_percentiles.values())
    assert all(value == Decimal(0) for value in result.probability_of_drawdown_exceeding.values())


def test_monte_carlo_percentiles_are_non_decreasing() -> None:
    trades = tuple(_trade("10" if i % 3 != 0 else "-30", i) for i in range(30))
    config = MonteCarloConfig(num_simulations=300, random_seed=99, min_trades_required=20)

    result = run_monte_carlo(trades, initial_capital=Decimal(10000), config=config)

    equity_values = [result.ending_equity_percentiles[f"p{p}"] for p in (5, 25, 50, 75, 95)]
    assert equity_values == sorted(equity_values)

    drawdown_values = [result.max_drawdown_percentiles[f"p{p}"] for p in (5, 25, 50, 75, 95)]
    assert drawdown_values == sorted(drawdown_values)


def test_monte_carlo_probability_of_drawdown_is_a_valid_fraction() -> None:
    trades = tuple(_trade("10" if i % 3 != 0 else "-30", i) for i in range(30))
    config = MonteCarloConfig(num_simulations=300, random_seed=3, min_trades_required=20)

    result = run_monte_carlo(trades, initial_capital=Decimal(10000), config=config)

    for probability in result.probability_of_drawdown_exceeding.values():
        assert Decimal(0) <= probability <= Decimal(1)


def test_monte_carlo_result_labels_its_assumptions() -> None:
    trades = tuple(_trade("10", i) for i in range(25))
    result = run_monte_carlo(trades, initial_capital=Decimal(10000), config=MonteCarloConfig(random_seed=1))
    assert len(result.assumptions) > 0
    assert any("not a forecast" in assumption.lower() for assumption in result.assumptions)


def test_monte_carlo_rejects_invalid_config() -> None:
    with pytest.raises(ValueError):
        MonteCarloConfig(num_simulations=0)
    with pytest.raises(ValueError):
        MonteCarloConfig(min_trades_required=1)


# --- Parameter stability ---


def _config(**overrides: object) -> BacktestConfig:
    fields: dict[str, object] = dict(
        strategy_id="test",
        strategy_version="1.0.0",
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=START,
        end=START + timedelta(days=100),
        initial_capital=Decimal(10000),
    )
    fields.update(overrides)
    return BacktestConfig(**fields)  # type: ignore[arg-type]


def _fake_result(ending_equity: str) -> BacktestResult:
    run = BacktestRun(config=_config(), run_id="fake", generated_at=START)
    equity_curve = (
        EquityObservation(timestamp=START, equity=Decimal(10000), cash=Decimal(10000), position=FLAT_POSITION),
        EquityObservation(
            timestamp=START + timedelta(days=1),
            equity=Decimal(ending_equity),
            cash=Decimal(ending_equity),
            position=FLAT_POSITION,
        ),
    )
    return BacktestResult(run=run, equity_curve=equity_curve, trades=(), final_position=FLAT_POSITION)


def test_run_parameter_stability_collects_one_point_per_grid_entry() -> None:
    grid = [{"fast_period": 5}, {"fast_period": 10}, {"fast_period": 15}]

    def run_backtest(params: dict[str, object]) -> BacktestResult:
        return _fake_result("10500")

    result = run_parameter_stability(grid, run_backtest=run_backtest)
    assert len(result.points) == 3
    assert result.points[0].parameters == {"fast_period": 5}


def test_run_parameter_stability_rejects_empty_grid() -> None:
    with pytest.raises(ValueError):
        run_parameter_stability([], run_backtest=lambda params: _fake_result("10000"))


def test_assess_stability_known_values() -> None:
    stable_points = tuple(
        ParameterStabilityPoint(parameters={"p": i}, metrics=compute_performance_metrics(_fake_result("10500")))
        for i in range(3)
    )
    stable_result = ParameterStabilityResult(points=stable_points)
    stable_score = assess_stability(stable_result, "total_return")
    assert stable_score == Decimal(1)  # identical metric across every point -> perfectly stable

    brittle_points = (
        ParameterStabilityPoint(parameters={"p": 0}, metrics=compute_performance_metrics(_fake_result("10500"))),
        ParameterStabilityPoint(parameters={"p": 1}, metrics=compute_performance_metrics(_fake_result("9000"))),
        ParameterStabilityPoint(parameters={"p": 2}, metrics=compute_performance_metrics(_fake_result("15000"))),
    )
    brittle_result = ParameterStabilityResult(points=brittle_points)
    brittle_score = assess_stability(brittle_result, "total_return")

    assert brittle_score is not None
    assert brittle_score < stable_score


def test_assess_stability_none_with_fewer_than_two_defined_values() -> None:
    points = (ParameterStabilityPoint(parameters={"p": 0}, metrics=compute_performance_metrics(_fake_result("10500"))),)
    result = ParameterStabilityResult(points=points)
    assert assess_stability(result, "total_return") is None


def test_assess_stability_none_when_metric_undefined_for_all_points() -> None:
    points = tuple(
        ParameterStabilityPoint(parameters={"p": i}, metrics=compute_performance_metrics(_fake_result("10500")))
        for i in range(3)
    )
    result = ParameterStabilityResult(points=points)
    assert assess_stability(result, "profit_factor") is None  # no trades -> always None
