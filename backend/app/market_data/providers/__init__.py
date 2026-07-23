"""Concrete market-data provider adapters.

Nothing outside this package may assume a specific vendor is in use — all
access goes through ``backend.app.market_data.provider.MarketDataProvider``
(ARCHITECTURE.md Section 7).
"""

from backend.app.market_data.providers.stooq import StooqProvider

__all__ = ["StooqProvider"]
