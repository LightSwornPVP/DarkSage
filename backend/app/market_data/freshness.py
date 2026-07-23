"""Freshness/staleness checks for data returned by a market-data provider.

Kept separate from ``shared/models`` deliberately: freshness is a
provider/adapter concern (how old is what the vendor just gave us?), not a
property of the ``Candle``/``Quote`` domain models themselves.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from shared.models.candle import Timeframe

# A timestamp more than this far in the future (relative to `now`) is never
# "fresh" — it's invalid. This tolerance only absorbs minor, expected clock
# skew between systems; it is not a grace period for genuinely future-dated
# data, which real market data should never produce.
DEFAULT_CLOCK_SKEW_TOLERANCE = timedelta(minutes=5)

# Conservative, fail-closed default staleness thresholds per timeframe, used
# whenever a caller (e.g. Scanner) doesn't supply an explicit max_age. Roughly
# a few bar-widths, with extra room for D1/W1 to absorb weekend/holiday market
# closures without misclassifying the last real trading session as stale.
_DEFAULT_MAX_AGE_BY_TIMEFRAME: dict[Timeframe, timedelta] = {
    Timeframe.M1: timedelta(minutes=5),
    Timeframe.M5: timedelta(minutes=15),
    Timeframe.M15: timedelta(minutes=45),
    Timeframe.M30: timedelta(minutes=90),
    Timeframe.H1: timedelta(hours=3),
    Timeframe.H4: timedelta(hours=12),
    Timeframe.D1: timedelta(days=4),
    Timeframe.W1: timedelta(days=10),
}


def default_max_age(timeframe: Timeframe) -> timedelta:
    """A conservative, fail-closed default staleness threshold for ``timeframe``.

    Used wherever Phase 1 needs "some" freshness enforcement but the caller
    hasn't configured an explicit threshold — freshness must be enabled by
    default, never silently skipped.
    """
    return _DEFAULT_MAX_AGE_BY_TIMEFRAME[timeframe]


def is_stale(
    timestamp: datetime,
    *,
    max_age: timedelta,
    now: datetime,
    clock_skew_tolerance: timedelta = DEFAULT_CLOCK_SKEW_TOLERANCE,
) -> bool:
    """Return True if ``timestamp`` is unusable as "current" data: either
    older than ``max_age``, or dated further into the future than
    ``clock_skew_tolerance`` allows (which real market data should never be —
    a future timestamp is treated as invalid/stale, not fresh).

    Fails closed (raises) rather than guessing when either datetime is naive,
    matching the timezone-aware-only rule enforced by ``Candle``/``Quote``.
    """
    if timestamp.tzinfo is None:
        raise ValueError("is_stale: timestamp must be timezone-aware")
    if now.tzinfo is None:
        raise ValueError("is_stale: now must be timezone-aware")
    if clock_skew_tolerance < timedelta(0):
        raise ValueError("is_stale: clock_skew_tolerance must be >= 0")

    age = now - timestamp
    if age < -clock_skew_tolerance:
        return True  # future-dated beyond tolerance -> invalid, not fresh
    return age > max_age
