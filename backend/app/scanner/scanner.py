"""``Scanner`` — runs deterministic filters over a supplied universe.

Provider-independent: callers pass already-fetched ``Candle`` series (e.g.
from a ``MarketDataProvider`` adapter plus Slice 1.5 normalization) — the
scanner itself never talks to a provider. No trading or execution action is
taken here; a ``ScanResult`` is research output only, same as a ``Signal``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone

from backend.app.indicators.engine import IndicatorEngine, validate_candle_series
from backend.app.indicators.errors import InsufficientDataError, InvalidCandleSeriesError
from backend.app.market_data.freshness import default_max_age, is_stale
from backend.app.scanner.filters import Filter
from backend.app.scanner.types import ScanCandidate, ScanContext, ScanResult
from shared.models.candle import Candle


class Scanner:
    """Evaluates every symbol in a universe against a fixed set of
    indicators and filters, failing safe per symbol rather than aborting
    the whole scan.

    Freshness enforcement is on by default: unless ``allow_stale_data_for_testing``
    is explicitly set, every candidate's latest candle is checked against
    ``max_data_age`` (or, if that's not given, a conservative default derived
    from the candle series' own timeframe) — there is no configuration under
    which stale or future-dated data is silently accepted.
    """

    def __init__(
        self,
        engine: IndicatorEngine,
        indicator_names: Sequence[str],
        filters: Sequence[Filter],
        *,
        max_data_age: timedelta | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        allow_stale_data_for_testing: bool = False,
    ) -> None:
        self._engine = engine
        self._indicator_names = tuple(indicator_names)
        self._filters = tuple(filters)
        self._max_data_age = max_data_age
        self._clock = clock
        self._allow_stale_data_for_testing = allow_stale_data_for_testing

    def scan(self, universe: Mapping[str, Sequence[Candle]]) -> ScanResult:
        candidates = tuple(self._scan_one(symbol, candles) for symbol, candles in universe.items())
        return ScanResult(candidates=candidates)

    def _scan_one(self, symbol: str, candles: Sequence[Candle]) -> ScanCandidate:
        requested_symbol = symbol.strip().upper()

        if not candles:
            return ScanCandidate(
                symbol=requested_symbol,
                latest_candle=None,
                eligible=False,
                block_reasons=("missing_data: no candles supplied",),
                indicators={},
            )

        try:
            validate_candle_series(candles)
        except InvalidCandleSeriesError as exc:
            return ScanCandidate(
                symbol=requested_symbol,
                latest_candle=None,
                eligible=False,
                block_reasons=(f"invalid_data: {exc}",),
                indicators={},
            )

        # validate_candle_series already guarantees every candle shares one
        # symbol, so checking the first is enough to catch a universe key
        # that doesn't match the data it was paired with — never rank one
        # security using another security's candles.
        actual_symbol = candles[0].symbol
        if actual_symbol != requested_symbol:
            return ScanCandidate(
                symbol=requested_symbol,
                latest_candle=None,
                eligible=False,
                block_reasons=(
                    f"symbol_mismatch: universe key '{requested_symbol}' does not match "
                    f"candle data symbol '{actual_symbol}'",
                ),
                indicators={},
            )

        latest_candle = candles[-1]
        block_reasons: list[str] = []

        if not self._allow_stale_data_for_testing:
            effective_max_age = (
                self._max_data_age if self._max_data_age is not None else default_max_age(latest_candle.timeframe)
            )
            now = self._clock()
            if is_stale(latest_candle.timestamp, max_age=effective_max_age, now=now):
                block_reasons.append(
                    f"stale_data: latest candle {latest_candle.timestamp.isoformat()} "
                    f"is not current relative to {now.isoformat()} (max age {effective_max_age})"
                )

        indicators = {}
        for name in self._indicator_names:
            try:
                indicators[name] = self._engine.compute(name, candles)
            except InsufficientDataError as exc:
                block_reasons.append(f"insufficient_history: {exc}")

        context = ScanContext(symbol=requested_symbol, latest_candle=latest_candle, indicators=indicators)
        for filt in self._filters:
            outcome = filt.evaluate(context)
            if not outcome.passed:
                block_reasons.append(outcome.reason or f"{filt.name}: blocked")

        return ScanCandidate(
            symbol=requested_symbol,
            latest_candle=latest_candle,
            eligible=len(block_reasons) == 0,
            block_reasons=tuple(block_reasons),
            indicators=indicators,
        )
