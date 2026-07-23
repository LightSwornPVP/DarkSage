"""Deterministic chronological candle-history primitives.

Kept separate from ``engine.py`` (which owns the top-level ``BacktestEngine``
orchestrator, and therefore depends on ``strategy``/``execution``) so that
``strategy/simulate.py`` can depend on ``BacktestStep`` without creating an
import cycle back through ``engine.py``.

The central anti-lookahead primitive is ``iter_backtest_steps``: at index
``i`` it hands out ``candles[: i + 1]`` and nothing else. There is no way
for a consumer to reach into ``candles[i + 1:]`` short of holding a
reference to the original sequence.

``BacktestConfig.start``/``end`` bound the *active* simulation window;
candles dated before ``start`` may still be supplied as warm-up context
(visible to indicators, but no trade decisions are made until ``start``).
Candles dated after ``end`` are rejected outright — there is no legitimate
reason to supply them, and silently truncating them would only hide a
caller's mistake.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from backend.app.backtesting.config import BacktestConfig, canonical_parameters
from backend.app.backtesting.errors import InsufficientHistoryError, InvalidHistoryError
from shared.models.candle import Candle


def validate_backtest_history(candles: Sequence[Candle], config: BacktestConfig) -> None:
    """Fail closed on any candle history a backtest cannot safely run over."""
    if not candles:
        raise InvalidHistoryError("no candles supplied for backtest")

    expected_symbol = config.symbol.strip().upper()
    symbols = {candle.symbol for candle in candles}
    if symbols != {expected_symbol}:
        raise InvalidHistoryError(
            f"candle history symbol(s) {sorted(symbols)} do not match config symbol '{expected_symbol}'"
        )

    timeframes = {candle.timeframe for candle in candles}
    if timeframes != {config.timeframe}:
        raise InvalidHistoryError(
            f"candle history timeframe(s) {sorted(t.value for t in timeframes)} do not match "
            f"config timeframe '{config.timeframe.value}'"
        )

    for previous, current in zip(candles, candles[1:], strict=False):
        if current.timestamp <= previous.timestamp:
            raise InvalidHistoryError(
                "candle history must be strictly ordered by ascending timestamp with no "
                f"duplicates (found {previous.timestamp} then {current.timestamp})"
            )

    if candles[-1].timestamp < config.start:
        raise InsufficientHistoryError(
            f"all supplied candles end at {candles[-1].timestamp.isoformat()}, before the "
            f"configured start {config.start.isoformat()}"
        )
    if any(candle.timestamp > config.end for candle in candles):
        raise InvalidHistoryError(f"candle history extends beyond the configured end {config.end.isoformat()}")


@dataclass(frozen=True, slots=True)
class BacktestStep:
    """One chronological step of the backtest: the current candle, and
    exactly the history that would have been visible at that instant."""

    index: int
    candle: Candle
    visible_candles: tuple[Candle, ...]
    is_active: bool


def iter_backtest_steps(candles: Sequence[Candle], config: BacktestConfig) -> Iterator[BacktestStep]:
    """Yield one ``BacktestStep`` per candle, in chronological order.

    ``visible_candles`` for step ``i`` is always exactly ``candles[: i + 1]``
    — never ``candles[i + 1 :]`` or anything computed from it.
    """
    validate_backtest_history(candles, config)
    for index, candle in enumerate(candles):
        yield BacktestStep(
            index=index,
            candle=candle,
            visible_candles=tuple(candles[: index + 1]),
            is_active=candle.timestamp >= config.start,
        )


def _hash_framed(hasher: "hashlib._Hash", value: str) -> None:
    """Feed ``value`` into ``hasher`` with an explicit big-endian
    length prefix, so consecutive fields can never collide the way bare
    concatenation can — e.g. ``close="1"`` + ``volume="123"`` and
    ``close="11"`` + ``volume="23"`` both naively concatenate to
    ``"1123"``, but their framed byte sequences differ because each
    field's exact length is encoded immediately before it."""
    encoded = value.encode("utf-8")
    hasher.update(len(encoded).to_bytes(8, "big"))
    hasher.update(encoded)


def compute_data_identity(candles: Sequence[Candle]) -> str:
    """A deterministic content hash of the actual candle data: count plus
    every OHLCV value and timestamp. This is the "actual historical-data
    identity" — ``config.data_source_id`` is optional caller-supplied
    metadata that can *supplement* this (e.g. distinguishing two vendors
    that happened to report identical prices) but must never substitute
    for it, since a caller could leave it unset or wrong.

    Each field is fed through ``_hash_framed`` (length-prefixed, never bare
    concatenation) so two materially different candle sets can never hash
    identically just because their field boundaries happen to line up
    (see ``_hash_framed``'s docstring for the exact collision this
    prevents). Candles are hashed in the order given — a caller supplying
    the same candles in a different order gets a different identity,
    which is correct: order is semantically meaningful for a chronological
    price series.
    """
    hasher = hashlib.sha256()
    _hash_framed(hasher, str(len(candles)))
    for candle in candles:
        _hash_framed(hasher, candle.symbol)
        _hash_framed(hasher, candle.timeframe.value)
        _hash_framed(hasher, candle.timestamp.isoformat())
        _hash_framed(hasher, str(candle.open))
        _hash_framed(hasher, str(candle.high))
        _hash_framed(hasher, str(candle.low))
        _hash_framed(hasher, str(candle.close))
        _hash_framed(hasher, str(candle.volume))
    return hasher.hexdigest()


def compute_run_id(config: BacktestConfig, candles: Sequence[Candle]) -> str:
    """A deterministic identifier derived from ``config`` AND the actual
    ``candles`` supplied — the same config run against materially different
    historical data must not collide on the same run id, and the same
    config + same data always yields the same run id, independent of
    wall-clock time.

    Every identity-relevant field is fed through ``_hash_framed``
    (length-prefixed, never delimiter-joined) in a fixed order, so two
    materially different configs can never collide just because a
    delimiter happened to appear inside a field value — e.g.
    ``strategy_id="a|b", strategy_version="c"`` versus
    ``strategy_id="a", strategy_version="b|c"`` would concatenate
    identically under naive ``"|".join(...)``, but their framed byte
    sequences differ because each field's exact length is encoded
    immediately before it (see ``_hash_framed``). Strategy parameters are
    hashed via ``canonical_parameters`` (type-preserving: ``True`` and
    ``1``, or ``Decimal("1")`` and ``1``, are never conflated).
    """
    hasher = hashlib.sha256()
    for field in (
        config.strategy_id,
        config.strategy_version,
        config.symbol,
        config.timeframe.value,
        config.start.isoformat(),
        config.end.isoformat(),
        str(config.initial_capital),
        repr(canonical_parameters(config.parameters)),
        str(config.execution_config.cost.commission_rate),
        str(config.execution_config.cost.spread),
        str(config.execution_config.cost.slippage_rate),
        config.execution_config.fill_timing.value,
        str(config.execution_config.position_sizing.equity_fraction),
        str(config.execution_config.position_sizing.max_participation_rate),
        str(config.random_seed),
        str(config.data_source_id),
        str(config.reproducibility_id),
        compute_data_identity(candles),
    ):
        _hash_framed(hasher, field)
    return hasher.hexdigest()[:16]
