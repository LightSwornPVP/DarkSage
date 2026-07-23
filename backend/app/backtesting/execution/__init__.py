"""Simulation-only execution: turns simulated order intents into simulated
fills, applying commissions, spread, slippage, and fill-timing rules. No
real broker adapter, no live order placement.
"""

from backend.app.backtesting.execution.fill import SimulatedFill
from backend.app.backtesting.execution.simulator import ExecutionSimulator

__all__ = ["ExecutionSimulator", "SimulatedFill"]
