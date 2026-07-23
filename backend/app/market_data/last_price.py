"""``LastPrice`` — last-trade-price-only data, structurally distinct from a
real bid/ask ``Quote``.

Some providers (e.g. Stooq's free tier) only expose a last-trade price, not
a real NBBO bid/ask. Representing that as a ``Quote`` with ``bid=ask=last``
would fabricate a zero spread that looks like real market microstructure
data but isn't — this type exists so that gap is structural and detectable,
not a value a caller has to remember to distrust.

``timestamp_basis`` records whether the timestamp's timezone is confirmed:
"verified" means it can be trusted as authoritative freshness evidence
(e.g. for live/production decisions); "unverified" means it cannot, and any
freshness-sensitive use of it must go through ``ensure_freshness_eligible``,
which fails closed rather than silently trusting an unconfirmed clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from backend.app.market_data.errors import ProviderDataError

TimestampBasis = Literal["verified", "unverified"]


@dataclass(frozen=True, slots=True)
class LastPrice:
    """A single last-trade-price snapshot — never a substitute for a real
    bid/ask ``Quote``."""

    symbol: str
    price: Decimal
    timestamp: datetime
    timestamp_basis: TimestampBasis


def ensure_freshness_eligible(last_price: LastPrice) -> None:
    """Raise if ``last_price``'s timestamp cannot be trusted as freshness
    evidence.

    Call this before using ``last_price.timestamp`` in any staleness/
    freshness check. There is no way to "opt in" around this for unverified
    data — if the timezone isn't confirmed, the timestamp fails closed
    rather than being used as if it were authoritative.
    """
    if last_price.timestamp_basis != "verified":
        raise ProviderDataError(
            f"{last_price.symbol}: last-price timestamp basis is "
            f"'{last_price.timestamp_basis}', not 'verified' — it cannot be used as "
            "authoritative evidence for a freshness/staleness decision"
        )
