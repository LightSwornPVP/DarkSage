"""Freshness/staleness checks for data returned by a market-data provider.

Kept separate from ``shared/models`` deliberately: freshness is a
provider/adapter concern (how old is what the vendor just gave us?), not a
property of the ``Candle``/``Quote`` domain models themselves.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def is_stale(timestamp: datetime, *, max_age: timedelta, now: datetime) -> bool:
    """Return True if ``timestamp`` is older than ``max_age`` relative to ``now``.

    Fails closed (raises) rather than guessing when either datetime is naive,
    matching the timezone-aware-only rule enforced by ``Candle``/``Quote``.
    """
    if timestamp.tzinfo is None:
        raise ValueError("is_stale: timestamp must be timezone-aware")
    if now.tzinfo is None:
        raise ValueError("is_stale: now must be timezone-aware")
    return (now - timestamp) > max_age
