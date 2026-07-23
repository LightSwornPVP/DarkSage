"""Phase 1 end-to-end integration test.

Exercises the full pipeline described in ARCHITECTURE.md Section 7:

    Provider -> Adapter -> Normalizer -> ... -> Scanner / Strategies

using a fake Transport (no real network) so a StooqProvider's raw CSV
response flows through normalization into Candle objects, then through the
indicator engine, the scanner's filters, and finally scoring/ranking — the
same objects at every step, no re-conversion or duplicated parsing logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.indicators.engine import IndicatorEngine
from backend.app.indicators.library import ATRIndicator, EMAIndicator, RSIIndicator, RelativeVolumeIndicator
from backend.app.indicators.registry import IndicatorRegistry
from backend.app.market_data.providers.stooq import StooqProvider
from backend.app.scanner.filters import IndicatorRangeFilter, MinimumVolumeFilter, PriceRangeFilter
from backend.app.scanner.scoring import MomentumComponent, ScanScorer, VolumeParticipationComponent
from backend.app.scanner.scanner import Scanner
from shared.models.candle import Timeframe

BASE_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)
NUM_DAYS = 30


def _history_csv(start_price: int) -> str:
    lines = ["Date,Open,High,Low,Close,Volume"]
    price = start_price
    for day in range(NUM_DAYS):
        # a mild, slightly noisy uptrend: mostly +1, occasional -1 pullback,
        # so RSI/momentum indicators see both gains and losses
        price += -1 if day % 7 == 0 and day > 0 else 1
        date = (BASE_DATE + timedelta(days=day)).date().isoformat()
        volume = 1_000_000 + (day % 5) * 100_000
        lines.append(f"{date},{price - 1}.00,{price + 1}.00,{price - 2}.00,{price}.00,{volume}")
    return "\n".join(lines) + "\n"


class _FakeTransport:
    def __init__(self, history_csv: str) -> None:
        self._history_csv = history_csv

    def fetch(self, url: str, *, timeout: float) -> str:
        assert "/q/d/l/" in url
        return self._history_csv


async def _no_sleep(_seconds: float) -> None:
    return None


async def test_provider_through_scanner_and_scoring_pipeline() -> None:
    provider = StooqProvider(transport=_FakeTransport(_history_csv(100)), sleep=_no_sleep)

    candles = await provider.get_candles("aapl", Timeframe.D1, limit=NUM_DAYS)

    assert len(candles) == NUM_DAYS
    assert all(candle.symbol == "AAPL" for candle in candles)  # canonical symbol, not vendor-suffixed
    assert isinstance(candles[0].close, Decimal)  # Decimal precision preserved through normalization

    registry = IndicatorRegistry()
    registry.register(EMAIndicator(9))
    registry.register(EMAIndicator(20))
    registry.register(RSIIndicator(14))
    registry.register(ATRIndicator(14))
    registry.register(RelativeVolumeIndicator(5))
    engine = IndicatorEngine(registry)

    scanner = Scanner(
        engine,
        indicator_names=["ema_9", "ema_20", "rsi_14", "atr_14", "rvol_5"],
        filters=[
            PriceRangeFilter(min_price=Decimal("1")),
            MinimumVolumeFilter(Decimal("500000")),
            IndicatorRangeFilter("rsi_14", "rsi", min_value=Decimal("1"), max_value=Decimal("99")),
        ],
        # Freshness is on by default (blocker 1) — pin the clock near the
        # synthetic candles' own dates rather than relying on wall-clock time.
        clock=lambda: candles[-1].timestamp + timedelta(hours=12),
    )

    scan_result = scanner.scan({"AAPL": candles})
    candidate = scan_result.candidates[0]

    assert candidate.symbol == "AAPL"
    assert candidate.eligible is True, candidate.block_reasons
    assert "ema_9" in candidate.indicators
    assert "rsi_14" in candidate.indicators

    scorer = ScanScorer([MomentumComponent("rsi_14"), VolumeParticipationComponent("rvol_5")])
    ranked = scorer.rank(scan_result)

    assert len(ranked) == 1
    assert ranked[0].symbol == "AAPL"
    assert ranked[0].eligible is True
    assert ranked[0].total_score is not None


async def test_pipeline_fails_safe_when_symbol_has_insufficient_history() -> None:
    # Only 5 candles: not enough for rsi_14 (warmup=15) or ema_20 (warmup=20).
    short_csv = "\n".join(
        ["Date,Open,High,Low,Close,Volume"]
        + [f"2026-01-{day:02d},99.00,101.00,98.00,100.00,1000000" for day in range(1, 6)]
    )
    provider = StooqProvider(transport=_FakeTransport(short_csv), sleep=_no_sleep)
    candles = await provider.get_candles("aapl", Timeframe.D1, limit=100)

    registry = IndicatorRegistry()
    registry.register(EMAIndicator(20))
    registry.register(RSIIndicator(14))
    engine = IndicatorEngine(registry)
    scanner = Scanner(engine, indicator_names=["ema_20", "rsi_14"], filters=[])

    result = scanner.scan({"AAPL": candles})
    candidate = result.candidates[0]

    assert candidate.eligible is False
    assert any("insufficient_history" in reason for reason in candidate.block_reasons)

    # A blocked candidate never ranks, even though scoring itself is still
    # computable on whatever partial indicator data exists (none, here).
    scorer = ScanScorer([MomentumComponent("rsi_14")])
    assert scorer.rank(result) == ()
