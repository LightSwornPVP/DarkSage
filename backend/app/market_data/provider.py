"""MarketDataProvider — common interface for all market-data providers.

See ARCHITECTURE.md Section 7 (Market Data Architecture). DarkSage must
not be tightly coupled to one market-data provider; this interface is the
adapter boundary. No concrete provider is implemented in this slice.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from shared.models.candle import Candle, Timeframe
from shared.models.quote import Quote


class MarketDataProvider(ABC):
    """Abstract base for every market-data provider adapter."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short, stable identifier for this provider."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """Return the latest quote for a symbol."""

    @abstractmethod
    async def get_candles(
        self, symbol: str, timeframe: Timeframe, *, limit: int = 100
    ) -> list[Candle]:
        """Return the most recent ``limit`` candles for a symbol/timeframe."""

    @abstractmethod
    async def get_historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return candles for a symbol/timeframe within an explicit date range."""

    @abstractmethod
    async def get_company_info(self, symbol: str) -> dict[str, str]:
        """Return basic company/instrument metadata for a symbol."""

    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> dict[str, float]:
        """Return fundamental data points for a symbol."""

    @abstractmethod
    async def get_news(self, symbol: str, *, limit: int = 10) -> list[dict[str, str]]:
        """Return recent news items related to a symbol."""

    @abstractmethod
    async def get_market_status(self) -> str:
        """Return the current market status (e.g. 'open', 'closed', 'pre-market')."""
