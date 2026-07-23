"""Deterministic backtest performance analytics.

Every field on ``PerformanceMetrics`` is ``None`` when mathematically
undefined for the given data (no trades, zero variance, zero losses, a
single equity observation, ...) — never a fabricated 0, NaN, or Infinity.

``win_rate`` in isolation must never be read as a measure of strategy
quality: a strategy can have a high win rate and still lose money (many
small wins, one huge loss) or a low win rate and be highly profitable
(few big wins, many small losses). Use ``profit_factor``/``expectancy``
alongside it, never instead of it.

Annualization assumptions (documented, not universal fact): standard
US-equities trading-calendar approximations — 252 trading days/year, a
~6.5 hour/390 minute regular session. Sample (n-1) standard deviation is
used for volatility/Sharpe/Sortino, since a backtest's returns are always a
finite sample, not a full population.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from backend.app.backtesting.types import BacktestResult, EquityObservation, SimulatedTrade
from shared.models.candle import Candle, Timeframe

_PERIODS_PER_YEAR: dict[Timeframe, Decimal] = {
    Timeframe.M1: Decimal(252 * 390),
    Timeframe.M5: Decimal(252 * 78),
    Timeframe.M15: Decimal(252 * 26),
    Timeframe.M30: Decimal(252 * 13),
    Timeframe.H1: Decimal(252 * 7),
    Timeframe.H4: Decimal(252 * 2),
    Timeframe.D1: Decimal(252),
    Timeframe.W1: Decimal(52),
}

_DAYS_PER_YEAR = Decimal("365.25")


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Deterministic performance/trade analytics for one ``BacktestResult``."""

    num_trades: int
    total_return: Decimal | None
    cagr: Decimal | None
    win_rate: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    win_loss_ratio: Decimal | None
    profit_factor: Decimal | None
    expectancy: Decimal | None
    max_drawdown: Decimal | None
    max_drawdown_duration: timedelta | None
    sharpe_ratio: Decimal | None
    sortino_ratio: Decimal | None
    volatility: Decimal | None
    exposure: Decimal | None
    average_holding_time: timedelta | None
    best_trade_pnl: Decimal | None
    worst_trade_pnl: Decimal | None
    average_r_multiple: Decimal | None


@dataclass(frozen=True, slots=True)
class TradeExcursion:
    """Maximum adverse/favorable excursion for one trade, as price moves
    against/for the position (always >= 0), computed from the historical
    path between its entry and exit."""

    mae: Decimal
    mfe: Decimal


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, start=Decimal(0)) / Decimal(len(values))


def _sample_std(values: Sequence[Decimal]) -> Decimal | None:
    """Sample (n-1) standard deviation — undefined (None) for fewer than 2
    values, since a spread cannot be meaningfully estimated from one point."""
    if len(values) < 2:
        return None
    mean = _mean(values)
    assert mean is not None
    variance = sum(((value - mean) ** 2 for value in values), start=Decimal(0)) / Decimal(len(values) - 1)
    return variance.sqrt()


def _equity_returns(equity_curve: Sequence[EquityObservation]) -> list[Decimal]:
    returns: list[Decimal] = []
    for previous, current in zip(equity_curve, equity_curve[1:], strict=False):
        if previous.equity == 0:
            continue  # cannot compute a percentage return from zero equity
        returns.append(current.equity / previous.equity - Decimal(1))
    return returns


def _total_return(initial_capital: Decimal, equity_curve: Sequence[EquityObservation]) -> Decimal | None:
    if not equity_curve or initial_capital == 0:
        return None
    return equity_curve[-1].equity / initial_capital - Decimal(1)


def _cagr(
    initial_capital: Decimal, equity_curve: Sequence[EquityObservation]
) -> Decimal | None:
    if len(equity_curve) < 2:
        return None
    total_return = _total_return(initial_capital, equity_curve)
    if total_return is None:
        return None
    growth_factor = Decimal(1) + total_return
    if growth_factor <= 0:
        return None  # a total wipeout has no real-valued annualized growth rate

    duration = equity_curve[-1].timestamp - equity_curve[0].timestamp
    years = Decimal(duration.total_seconds()) / (_DAYS_PER_YEAR * Decimal(86400))
    if years <= 0:
        return None

    try:
        return growth_factor ** (Decimal(1) / years) - Decimal(1)
    except InvalidOperation:
        return None


def max_drawdown_from_values(values: Sequence[Decimal]) -> Decimal:
    """The core peak-to-trough drawdown calculation on a plain sequence of
    values, with no notion of time. Shared by equity-curve metrics (below,
    which additionally track *when* the max drawdown occurred — meaningful
    only because equity observations carry real timestamps) and Monte Carlo
    path analysis (``robustness.py``, whose simulated paths are just
    reordered/resampled Decimal amounts with no coherent timeline to
    attach a duration to).
    """
    if not values:
        return Decimal(0)
    peak = values[0]
    max_drawdown = Decimal(0)
    for value in values:
        if value > peak:
            peak = value
        elif peak > 0:
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
    return max_drawdown


def _max_drawdown(equity_curve: Sequence[EquityObservation]) -> tuple[Decimal | None, timedelta | None]:
    if not equity_curve:
        return None, None
    peak = equity_curve[0].equity
    peak_time = equity_curve[0].timestamp
    max_drawdown = Decimal(0)
    max_drawdown_duration: timedelta | None = None

    for observation in equity_curve:
        if observation.equity >= peak:
            peak = observation.equity
            peak_time = observation.timestamp
            continue
        if peak == 0:
            continue
        drawdown = (peak - observation.equity) / peak
        duration_since_peak = observation.timestamp - peak_time
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_drawdown_duration = duration_since_peak

    return max_drawdown, max_drawdown_duration


def _exposure(equity_curve: Sequence[EquityObservation]) -> Decimal | None:
    """Fraction of observed bars with a non-flat position — a bar-count
    approximation of time-in-market, not exact wall-clock time (bars can
    span unequal real time, e.g. weekends)."""
    if not equity_curve:
        return None
    bars_in_market = sum(1 for observation in equity_curve if not observation.position.is_flat)
    return Decimal(bars_in_market) / Decimal(len(equity_curve))


def _trade_pnls(trades: Sequence[SimulatedTrade]) -> tuple[list[Decimal], list[Decimal]]:
    wins = [trade.pnl for trade in trades if trade.pnl > 0]
    losses = [trade.pnl for trade in trades if trade.pnl < 0]
    return wins, losses


def compute_performance_metrics(result: BacktestResult) -> PerformanceMetrics:
    """Compute deterministic performance analytics for a completed backtest."""
    config = result.config
    equity_curve = result.equity_curve
    trades = result.trades
    periods_per_year = _PERIODS_PER_YEAR[config.timeframe]

    returns = _equity_returns(equity_curve)
    max_drawdown, max_drawdown_duration = _max_drawdown(equity_curve)

    std_return = _sample_std(returns)
    mean_return = _mean(returns)
    sharpe_ratio = (
        (mean_return / std_return) * periods_per_year.sqrt()
        if mean_return is not None and std_return is not None and std_return != 0
        else None
    )
    downside_returns = [r for r in returns if r < 0]
    downside_std = _sample_std(downside_returns)
    sortino_ratio = (
        (mean_return / downside_std) * periods_per_year.sqrt()
        if mean_return is not None and downside_std is not None and downside_std != 0
        else None
    )
    volatility = std_return * periods_per_year.sqrt() if std_return is not None else None

    wins, losses = _trade_pnls(trades)
    win_rate = Decimal(len(wins)) / Decimal(len(trades)) if trades else None
    average_win = _mean(wins)
    average_loss = _mean(losses)
    win_loss_ratio = (
        average_win / abs(average_loss)
        if average_win is not None and average_loss is not None and average_loss != 0
        else None
    )
    gross_profit = sum(wins, start=Decimal(0))
    gross_loss = abs(sum(losses, start=Decimal(0)))
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else None
    expectancy = _mean([trade.pnl for trade in trades])

    holding_times = [trade.exit_time - trade.entry_time for trade in trades]
    average_holding_time = (
        sum(holding_times, start=timedelta(0)) / len(holding_times) if holding_times else None
    )

    r_multiples: list[Decimal] = []
    for trade in trades:
        if trade.stop_price is None:
            continue
        risk_per_share = abs(trade.entry_price - trade.stop_price)
        if risk_per_share == 0:
            continue
        r_multiples.append(trade.pnl / (risk_per_share * trade.quantity))

    return PerformanceMetrics(
        num_trades=len(trades),
        total_return=_total_return(config.initial_capital, equity_curve),
        cagr=_cagr(config.initial_capital, equity_curve),
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        win_loss_ratio=win_loss_ratio,
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_drawdown=max_drawdown,
        max_drawdown_duration=max_drawdown_duration,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        volatility=volatility,
        exposure=_exposure(equity_curve),
        average_holding_time=average_holding_time,
        best_trade_pnl=max((trade.pnl for trade in trades), default=None),
        worst_trade_pnl=min((trade.pnl for trade in trades), default=None),
        average_r_multiple=_mean(r_multiples),
    )


def compute_trade_excursion(trade: SimulatedTrade, candles: Sequence[Candle]) -> TradeExcursion | None:
    """Maximum adverse/favorable excursion for ``trade``, scanning
    ``candles`` between its entry and exit (inclusive). Returns ``None`` if
    no candles fall in that window — MAE/MFE is only computed "where the
    historical path allows it", never fabricated.
    """
    window = [candle for candle in candles if trade.entry_time <= candle.timestamp <= trade.exit_time]
    if not window:
        return None

    is_long = trade.direction.value == "long"
    worst_price = min(candle.low for candle in window) if is_long else max(candle.high for candle in window)
    best_price = max(candle.high for candle in window) if is_long else min(candle.low for candle in window)

    if is_long:
        mae = max(Decimal(0), trade.entry_price - worst_price)
        mfe = max(Decimal(0), best_price - trade.entry_price)
    else:
        mae = max(Decimal(0), worst_price - trade.entry_price)
        mfe = max(Decimal(0), trade.entry_price - best_price)

    return TradeExcursion(mae=mae, mfe=mfe)
