"""``Strategy`` — the interface every backtestable strategy implements.

A strategy is pure decision logic: given a ``StrategyContext`` (which
cannot contain future information), return one ``StrategyDecision``. It has
no way to place a real order — see ``intent.py`` for why simulated intents
are structurally incapable of reaching a real Execution Engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from backend.app.backtesting.config import StrategyParameterValue
from backend.app.backtesting.strategy.context import StrategyContext
from backend.app.backtesting.strategy.intent import StrategyDecision


class Strategy(ABC):
    """Abstract base for every backtestable strategy."""

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """Short, stable identifier (e.g. 'reference-ma-crossover')."""

    @property
    @abstractmethod
    def strategy_version(self) -> str:
        """Version string for this strategy's logic — part of run
        reproducibility metadata."""

    @property
    @abstractmethod
    def parameters(self) -> Mapping[str, StrategyParameterValue]:
        """The concrete parameter values this instance was configured
        with — part of run reproducibility metadata."""

    @property
    @abstractmethod
    def warmup_period(self) -> int:
        """Minimum number of visible candles needed before this strategy
        can produce a non-HOLD decision."""

    @abstractmethod
    def decide(self, context: StrategyContext) -> StrategyDecision:
        """Return this strategy's decision for the current bar, using only
        ``context.visible_candles`` and ``context.position``."""
