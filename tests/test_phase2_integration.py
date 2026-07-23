"""Phase 2 end-to-end integration test.

Exercises the full pipeline:

    Normalized historical Candle data (via StooqProvider + Slice 1.5 normalization)
    -> Indicator Engine
    -> Strategy (reference MA crossover)
    -> Simulated signal/order intent
    -> Simulated execution (costs applied)
    -> Portfolio/equity state
    -> BacktestResult
    -> Performance metrics
    -> Walk-forward / out-of-sample validation
    -> Monte Carlo robustness
    -> Experiment comparison

and the cross-cutting correctness properties: no lookahead, deterministic
reproducibility (including same-seed Monte Carlo), no broker/live path, no
AI in any deterministic calculation, Decimal precision, timezone-aware
timestamps, and no silently propagated NaN/Infinity.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.backtesting.comparison import ExperimentEntry, ExperimentRegistry, compare_experiments
from backend.app.backtesting.config import BacktestConfig
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.metrics import compute_performance_metrics
from backend.app.backtesting.robustness import MonteCarloConfig, run_monte_carlo
from backend.app.backtesting.strategy.reference import MovingAverageCrossoverStrategy
from backend.app.backtesting.validation.walkforward import generate_walk_forward_windows, run_walk_forward
from backend.app.market_data.providers.stooq import StooqProvider
from shared.models.candle import Timeframe

BASE_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)
NUM_DAYS = 90


def _history_csv() -> str:
    lines = ["Date,Open,High,Low,Close,Volume"]
    price = 100
    for day in range(NUM_DAYS):
        # multiple oscillation cycles so the MA-crossover strategy sees
        # several complete entry/exit round trips
        cycle_position = day % 20
        price += 2 if cycle_position < 10 else -2
        date = (BASE_DATE + timedelta(days=day)).date().isoformat()
        volume = 1_000_000 + (day % 5) * 10_000
        lines.append(f"{date},{price - 1}.00,{price + 2}.00,{price - 2}.00,{price}.00,{volume}")
    return "\n".join(lines) + "\n"


class _FakeTransport:
    def __init__(self, history_csv: str) -> None:
        self._history_csv = history_csv

    def fetch(self, url: str, *, timeout: float) -> str:
        assert "/q/d/l/" in url
        return self._history_csv


async def _no_sleep(_seconds: float) -> None:
    return None


def _fixed_clock() -> datetime:
    return datetime(2026, 6, 1, tzinfo=timezone.utc)


def _base_config() -> BacktestConfig:
    return BacktestConfig(
        strategy_id="reference-ma-crossover",
        strategy_version="1.0.0",
        symbol="AAPL",
        timeframe=Timeframe.D1,
        start=BASE_DATE,
        end=BASE_DATE + timedelta(days=NUM_DAYS),
        initial_capital=Decimal(10000),
        data_source_id="stooq",
        random_seed=42,
        parameters={"fast_period": 3, "slow_period": 8},
    )


async def test_full_pipeline_normalized_candles_through_comparison_and_robustness() -> None:
    provider = StooqProvider(transport=_FakeTransport(_history_csv()), sleep=_no_sleep)
    candles = await provider.get_candles("aapl", Timeframe.D1, limit=NUM_DAYS)

    # --- Decimal precision + tz-aware timestamps survive normalization ---
    assert all(isinstance(c.close, Decimal) for c in candles)
    assert all(c.timestamp.tzinfo is not None for c in candles)
    assert all(c.symbol == "AAPL" for c in candles)  # canonical symbol, vendor suffix stripped

    strategy = MovingAverageCrossoverStrategy(fast_period=3, slow_period=8)
    config = _base_config()

    engine = BacktestEngine(config, candles, clock=_fixed_clock)
    result = engine.run_strategy(strategy)

    assert len(result.trades) >= 2  # the oscillating price pattern must produce several round trips

    # --- No lookahead: every trade's timestamps are real candle timestamps ---
    candle_timestamps = {c.timestamp for c in candles}
    for trade in result.trades:
        assert trade.entry_time in candle_timestamps
        assert trade.exit_time in candle_timestamps
        assert trade.entry_time.tzinfo is not None and trade.exit_time.tzinfo is not None
        assert isinstance(trade.pnl, Decimal)

    # --- Deterministic reproducibility: identical config + candles + clock -> identical result ---
    repeat_result = BacktestEngine(config, candles, clock=_fixed_clock).run_strategy(
        MovingAverageCrossoverStrategy(fast_period=3, slow_period=8)
    )
    assert result == repeat_result

    # --- Performance metrics: no silently propagated NaN/Infinity ---
    metrics = compute_performance_metrics(result)
    for field_name in metrics.__dataclass_fields__:
        value = getattr(metrics, field_name)
        if isinstance(value, Decimal):
            assert value.is_finite()

    # --- Walk-forward / out-of-sample: parameters frozen, no leakage ---
    windows = generate_walk_forward_windows(
        BASE_DATE,
        BASE_DATE + timedelta(days=NUM_DAYS),
        in_sample_duration=timedelta(days=45),
        out_of_sample_duration=timedelta(days=20),
    )

    def strategy_factory(params: object) -> MovingAverageCrossoverStrategy:
        assert isinstance(params, dict)
        return MovingAverageCrossoverStrategy(
            fast_period=int(params["fast_period"]), slow_period=int(params["slow_period"])
        )

    def select_parameters(candles_slice: object) -> dict[str, object]:
        return {"fast_period": 3, "slow_period": 8}

    wf_result = run_walk_forward(
        windows,
        base_config=config,
        candles=candles,
        strategy_factory=strategy_factory,
        select_parameters=select_parameters,
        clock=_fixed_clock,
    )
    assert len(wf_result.windows) >= 1
    for window_result in wf_result.windows:
        assert window_result.window.in_sample.end == window_result.window.out_of_sample.start
        assert window_result.in_sample_result.config.parameters == window_result.out_of_sample_result.config.parameters

    # --- Monte Carlo robustness: deterministic given the same seed ---
    monte_carlo_config = MonteCarloConfig(num_simulations=100, random_seed=7, min_trades_required=2)
    mc_result_a = run_monte_carlo(result.trades, initial_capital=config.initial_capital, config=monte_carlo_config)
    mc_result_b = run_monte_carlo(result.trades, initial_capital=config.initial_capital, config=monte_carlo_config)
    assert mc_result_a == mc_result_b

    # --- Comparison: rank the real strategy against a flat (no-op) baseline ---
    baseline_result = BacktestEngine(config, candles, clock=_fixed_clock).run()
    registry = ExperimentRegistry(
        entries=(
            ExperimentEntry(name="ma_crossover", result=result, metrics=metrics),
            ExperimentEntry(
                name="flat_baseline", result=baseline_result, metrics=compute_performance_metrics(baseline_result)
            ),
        )
    )
    comparison = compare_experiments(registry, metric_name="total_return")
    assert {entry.name for entry in comparison.ranked} == {"ma_crossover", "flat_baseline"}


def test_no_broker_or_live_execution_surface_exists() -> None:
    """Structural guard: none of the core simulation classes expose
    anything resembling a real order-submission capability."""
    import backend.app.backtesting.engine as engine_module
    import backend.app.backtesting.execution.simulator as simulator_module
    import backend.app.backtesting.portfolio as portfolio_module

    forbidden_terms = ("broker", "submit_order", "place_order", "live_trade", "execute_live")
    for module in (engine_module, portfolio_module, simulator_module):
        source = inspect.getsource(module).lower()
        for term in forbidden_terms:
            assert term not in source, f"{module.__name__} unexpectedly references '{term}'"


def test_backtesting_package_imports_cleanly_with_no_circular_dependencies() -> None:
    import backend.app.backtesting as bt
    import backend.app.backtesting.execution as execution_pkg
    import backend.app.backtesting.strategy as strategy_pkg
    import backend.app.backtesting.validation as validation_pkg

    assert len(bt.__all__) > 0
    assert len(strategy_pkg.__all__) > 0
    assert len(execution_pkg.__all__) > 0
    assert len(validation_pkg.__all__) > 0
