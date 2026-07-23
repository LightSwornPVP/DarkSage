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
from backend.app.market_data.freshness import is_stale
from backend.app.scanner.filters import Filter
from backend.app.scanner.types import ScanCandidate, ScanContext, ScanResult
from shared.models.candle import Candle


class Scanner:
    """Evaluates every symbol in a universe against a fixed set of
    indicators and filters, failing safe per symbol rather than aborting
    the whole scan."""

    def __init__(
        self,
        engine: IndicatorEngine,
        indicator_names: Sequence[str],
        filters: Sequence[Filter],
        *,
        max_data_age: timedelta | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._engine = engine
        self._indicator_names = tuple(indicator_names)
        self._filters = tuple(filters)
        self._max_data_age = max_data_age
        self._clock = clock

    def scan(self, universe: Mapping[str, Sequence[Candle]]) -> ScanResult:
        candidates = tuple(self._scan_one(symbol, candles) for symbol, candles in universe.items())
        return ScanResult(candidates=candidates)

    def _scan_one(self, symbol: str, candles: Sequence[Candle]) -> ScanCandidate:
        if not candles:
            return ScanCandidate(
                symbol=symbol,
                latest_candle=None,
                eligible=False,
                block_reasons=("missing_data: no candles supplied",),
                indicators={},
            )

        try:
            validate_candle_series(candles)
        except InvalidCandleSeriesError as exc:
            return ScanCandidate(
                symbol=symbol,
                latest_candle=None,
                eligible=False,
                block_reasons=(f"invalid_data: {exc}",),
                indicators={},
            )

        latest_candle = candles[-1]
        block_reasons: list[str] = []

        if self._max_data_age is not None:
            now = self._clock()
            if is_stale(latest_candle.timestamp, max_age=self._max_data_age, now=now):
                block_reasons.append(
                    f"stale_data: latest candle {latest_candle.timestamp.isoformat()} "
                    f"exceeds max age {self._max_data_age}"
                )

        indicators = {}
        for name in self._indicator_names:
            try:
                indicators[name] = self._engine.compute(name, candles)
            except InsufficientDataError as exc:
                block_reasons.append(f"insufficient_history: {exc}")

        context = ScanContext(symbol=symbol, latest_candle=latest_candle, indicators=indicators)
        for filt in self._filters:
            outcome = filt.evaluate(context)
            if not outcome.passed:
                block_reasons.append(outcome.reason or f"{filt.name}: blocked")

        return ScanCandidate(
            symbol=symbol,
            latest_candle=latest_candle,
            eligible=len(block_reasons) == 0,
            block_reasons=tuple(block_reasons),
            indicators=indicators,
        )
