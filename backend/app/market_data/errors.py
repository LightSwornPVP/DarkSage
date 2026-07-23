"""Provider-independent error taxonomy for market-data adapters.

Every concrete ``MarketDataProvider`` implementation must raise one of these
instead of leaking a vendor-specific exception type, so callers never need
to know which provider is behind the interface (ARCHITECTURE.md Section 7).
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for all market-data provider failures."""


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the configured timeout."""


class ProviderRateLimitedError(ProviderError):
    """The provider rejected the request because of rate limiting."""


class ProviderUnavailableError(ProviderError):
    """The provider is unreachable, or failed with a server-side error."""


class ProviderDataError(ProviderError):
    """The provider responded, but the payload could not be parsed or
    normalized into a domain model."""


class StaleDataError(ProviderError):
    """The freshest data the provider returned is older than the caller's
    configured freshness threshold."""


class ProviderUnsupportedOperationError(ProviderError):
    """This provider adapter does not implement the requested operation.

    Raised instead of fabricating a plausible-looking result, so callers
    fail closed rather than silently receiving invented data.
    """
