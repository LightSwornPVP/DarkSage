"""Deterministic, provider-independent backtesting and Strategy Lab
foundation (Phase 2). Simulation only — see ARCHITECTURE.md Section 14 for
the canonical TradeValidationPipeline; nothing here is, or feeds, a real
broker/execution path.
"""

from backend.app.backtesting.config import (
    BacktestConfig,
    CostConfig,
    ExecutionConfig,
    FillTiming,
    PositionSizingConfig,
    StrategyParameterValue,
)
from backend.app.backtesting.engine import (
    BacktestEngine,
    BacktestStep,
    compute_run_id,
    iter_backtest_steps,
    validate_backtest_history,
)
from backend.app.backtesting.errors import (
    BacktestError,
    InsufficientHistoryError,
    InvalidBacktestConfigError,
    InsufficientSampleSizeError,
    InvalidExecutionConfigError,
    InvalidHistoryError,
    InvalidPartitionError,
)
from backend.app.backtesting.execution import ExecutionSimulator, SimulatedFill
from backend.app.backtesting.metrics import (
    PerformanceMetrics,
    TradeExcursion,
    compute_performance_metrics,
    compute_trade_excursion,
)
from backend.app.backtesting.portfolio import Portfolio
from backend.app.backtesting.robustness import (
    MonteCarloConfig,
    MonteCarloResult,
    ParameterStabilityPoint,
    ParameterStabilityResult,
    assess_stability,
    run_monte_carlo,
    run_parameter_stability,
)
from backend.app.backtesting.validation import (
    DatePartition,
    WalkForwardResult,
    WalkForwardWindow,
    WalkForwardWindowResult,
    generate_walk_forward_windows,
    run_walk_forward,
    split_periods,
    validate_no_overlap,
)
from backend.app.backtesting.types import (
    FLAT_POSITION,
    BacktestResult,
    BacktestRun,
    EquityObservation,
    PositionState,
    SimulatedTrade,
)

__all__ = [
    "FLAT_POSITION",
    "BacktestConfig",
    "BacktestEngine",
    "BacktestError",
    "BacktestResult",
    "BacktestRun",
    "BacktestStep",
    "CostConfig",
    "DatePartition",
    "EquityObservation",
    "ExecutionConfig",
    "ExecutionSimulator",
    "FillTiming",
    "InsufficientHistoryError",
    "InsufficientSampleSizeError",
    "InvalidBacktestConfigError",
    "InvalidExecutionConfigError",
    "InvalidHistoryError",
    "InvalidPartitionError",
    "MonteCarloConfig",
    "MonteCarloResult",
    "ParameterStabilityPoint",
    "ParameterStabilityResult",
    "PerformanceMetrics",
    "Portfolio",
    "PositionSizingConfig",
    "PositionState",
    "SimulatedFill",
    "SimulatedTrade",
    "StrategyParameterValue",
    "TradeExcursion",
    "WalkForwardResult",
    "WalkForwardWindow",
    "WalkForwardWindowResult",
    "assess_stability",
    "compute_performance_metrics",
    "compute_run_id",
    "compute_trade_excursion",
    "generate_walk_forward_windows",
    "iter_backtest_steps",
    "run_monte_carlo",
    "run_parameter_stability",
    "run_walk_forward",
    "split_periods",
    "validate_backtest_history",
    "validate_no_overlap",
]
