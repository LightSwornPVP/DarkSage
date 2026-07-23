# DarkSage Trading Rules

## Purpose

These rules apply to backtesting, shadow trading, paper trading, future live trading, strategy evaluation, portfolio execution, and Auto-Trader behavior.

No AI agent, strategy, broker adapter, or UI action may bypass these rules.

## Core Rules

1. Development and testing are paper-trading only.
2. AI may propose trades but may never directly submit broker orders, and has no authority to directly access or call the Execution Engine or Broker Adapter. This applies identically to every configured AI provider — local or cloud, regardless of vendor.
3. Every trade must pass through the canonical TradeValidationPipeline in full (ARCHITECTURE.md §14) — no stage may be skipped, reordered, renamed, or duplicated.
4. Win rate alone is never sufficient to judge a strategy.
5. Small sample sizes must not be presented as strong evidence.
6. Backtests must protect against look-ahead bias, survivorship bias, data leakage, invalid fills, and unrealistic liquidity assumptions.
7. Every strategy must be versioned.
8. Strategy performance must be segmented by strategy, symbol, sector, timeframe, market regime, instrument, entry method, exit method, time of day, and day of week where relevant.
9. Strategy DNA must be based on measured statistical evidence, not AI guessing.
10. The system must fail closed when critical market data, broker state, risk state, or permissions are uncertain.

## Trading Modes

DarkSage supports:

- Day Trading
- Swing Trading
- Position Trading
- Long-Term Investing
- Custom Trading Modes

Each mode has separate strategy preferences, timeframes, risk rules, holding periods, and performance statistics.

## Strategy Promotion

Strategies progress through:

1. Experimental
2. Backtest
3. Validation
4. Out-of-sample
5. Walk-forward
6. Shadow
7. Paper Auto-Trading
8. Limited Live
9. Approved Live

Strategies may be demoted if performance deteriorates.

## Risk Rules

DarkSage must enforce:

- Maximum risk per trade
- Maximum daily loss
- Maximum weekly loss
- Maximum position size
- Maximum number of open positions
- Sector concentration
- Correlated exposure
- Portfolio risk budget
- Strategy drawdown limits
- Liquidity requirements
- Spread limits
- Volatility constraints
- Event-risk rules

No trade may be placed without a defined maximum-loss model.

## Portfolio Risk

DarkSage must detect when multiple positions represent the same effective risk.

Example:

- NVDA
- AMD
- AVGO
- SMH
- QQQ

These may be strongly correlated and must not be treated as independent diversification.

## Signal Grades

Signals may receive:

- A+
- A
- B
- C
- D

Auto-Trader permissions may restrict which grades can trade.

Grades must be based on measurable inputs.

## Why-Trade / Why-Not-Trade

Every accepted or rejected signal must include reasons.

Possible rejection reasons include:

- Poor risk/reward
- Weak expectancy
- Insufficient sample size
- Earnings risk
- Low liquidity
- Wide spread
- Market regime mismatch
- Sector concentration
- Correlated exposure
- Risk budget exhausted
- Stale data
- Bad data
- Strategy suspended

## AI Abstention

AI is allowed to return:

- No trade
- Insufficient confidence
- Conflicting evidence
- More data required

Not trading is a valid decision.

## Data Integrity

Trading must pause when critical data is unreliable.

Examples:

- Missing candles
- Stale quotes
- Provider outage
- Invalid prices
- Broken timestamps
- Suspicious volume
- Corrupt corporate-action adjustments

## Order Validation

Before submission:

- Symbol must be valid
- Instrument must be permitted
- Quantity must be valid
- Buying power must be sufficient
- Risk limits must pass
- Market state must be valid
- Data must be fresh
- Duplicate-order check must pass

## Duplicate Order Protection

Every order must have a unique execution identifier.

Retries must not unintentionally duplicate orders.

## Paper Broker

Initial execution uses paper trading only.

The paper environment should simulate:

- Buying power
- Positions
- Fills
- Partial fills where possible
- Slippage
- Fees
- Stops
- Targets
- P/L

Paper results must not be represented as guaranteed live results.

## Shadow Trading

Shadow trades do not reach the broker.

They may test:

- Alternate strategies
- Alternate entries
- Alternate exits
- Alternate position sizes
- Alternate instruments

## Emergency Stop

Emergency Stop must:

- Block all new orders immediately
- Cancel pending entry orders
- Continue monitoring existing positions

Any authorized DarkSage client may trigger it.

## Emergency Flatten

Emergency Flatten may:

- Block new orders
- Cancel open orders
- Close active positions according to emergency rules

In live mode, it must require strong authentication.

## Mobile Control

The phone app must be able to stop Auto-Trading even if Auto-Trade was enabled on desktop.

Auto-Trader state lives in the backend.

Stopping must be easier than enabling live trading.

## Broker Reconciliation

DarkSage must compare internal state with broker state:

- Positions
- Cash
- Open orders
- Filled orders
- Average prices

If reconciliation fails:

- Pause new trading
- Alert the user
- Record an audit event

## Live Trading Requirements

Before live trading:

- Paper performance must be acceptable
- Strategy promotion requirements must pass
- Security review must pass
- Broker reconciliation must pass
- Kill switch must pass testing
- Data health checks must pass
- Duplicate-order prevention must pass
- Monitoring must be active

Live trading must be explicitly enabled.

## Broker Permissions

DarkSage must use the minimum permissions necessary.

The app must never require:

- Withdrawal permission
- Unrelated transfer permission

Separate credentials must be used for paper and live.

## Audit Trail

Every trade decision must record:

- Timestamp
- Market data snapshot
- Indicators
- Strategy
- Strategy version
- Signal score
- AI analysis
- Risk decision
- Permission decision
- Portfolio decision
- Order request
- Broker response
- Fill
- Exit
- Final result

## Core Trading Rule

No trade is valid unless it passes:

- Strategy rules
- Data-quality rules
- Risk rules
- Permissions rules
- Portfolio rules
- Execution rules

AI is advisory. Deterministic safety systems have final authority.
