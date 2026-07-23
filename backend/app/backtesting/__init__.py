"""Deterministic, provider-independent backtesting and Strategy Lab
foundation (Phase 2). Simulation only — see ARCHITECTURE.md Section 14 for
the canonical TradeValidationPipeline; nothing here is, or feeds, a real
broker/execution path.
"""

from backend.app.backtesting.config import BacktestConfig, CostConfig, StrategyParameterValue
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
    InvalidExecutionConfigError,
    InvalidHistoryError,
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
    "EquityObservation",
    "InsufficientHistoryError",
    "InvalidBacktestConfigError",
    "InvalidExecutionConfigError",
    "InvalidHistoryError",
    "PositionState",
    "SimulatedTrade",
    "StrategyParameterValue",
    "compute_run_id",
    "iter_backtest_steps",
    "validate_backtest_history",
]
