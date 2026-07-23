# DarkSage Project Specification

## 1. Project Vision

DarkSage is a cross-platform market intelligence, trading research, portfolio, backtesting, and automated trading platform.

The platform is designed to:

- Scan and analyze a broad stock universe, initially focused on the S&P 500.
- Generate transparent trading signals with entries, stops, targets, confidence, and reasoning.
- Support multiple trading styles:
  - Day trading
  - Swing trading
  - Position trading
  - Long-term investing
  - Custom trading modes
- Support portfolio construction and optimization.
- Backtest strategies across historical data.
- Track strategy win/loss rates and other performance metrics.
- Learn which strategies historically perform best for:
  - Specific stocks
  - Sectors
  - Market regimes
  - Timeframes
  - Instrument types
- Use local AI by default to minimize recurring cost.
- Use cloud AI only when explicitly selected or when deeper analysis is justified.
- Begin with paper trading only.
- Support future live trading after extensive validation and safety controls.

---

## 2. Core Design Principles

### 2.1 Cheap-First Architecture

DarkSage should avoid paid services wherever a reliable free or local alternative exists.

Priority order:

1. Deterministic local code
2. Local AI
3. Free market-data/API tiers
4. Paid APIs only when proven necessary
5. Cloud AI only when value justifies cost

The system must never use expensive AI calls to perform calculations that deterministic code can perform reliably.

### 2.2 Paper Trading First

Development and testing must use paper trading only.

Live trading will remain disabled until:

- Backtests pass validation
- Out-of-sample testing passes
- Shadow testing passes
- Paper forward testing passes
- Risk controls are verified
- Execution safeguards are verified
- Live credentials are explicitly configured and unlocked

### 2.3 AI Never Directly Controls the Broker

The AI may create or explain a Trade Proposal.

Every trade must pass through the canonical TradeValidationPipeline, defined once in ARCHITECTURE.md §14 and repeated here exactly:

```
AI / Strategy Engine
→ Trade Proposal
→ Signal Validator
→ Strategy Validation
→ Risk Engine
→ Permissions Engine
→ Portfolio / Exposure Checks
→ Buying Power Checks
→ Market Condition Checks
→ Order Validation
→ Execution Engine
→ Broker Adapter
```

AI has no authority to bypass any stage, and no authority to directly access or call the Execution Engine or Broker Adapter under any circumstance.

---

## 3. Trading Modes

### 3.1 Day Trading

Focus:

- Intraday timeframes
- Momentum
- Opening range breakouts
- VWAP
- Relative volume
- Intraday support/resistance
- News catalysts
- Liquidity
- Tight risk controls

Optional rule:

- Close all positions before market close

### 3.2 Swing Trading

Focus:

- 1H
- 4H
- Daily
- Breakouts
- Momentum
- Pullbacks
- Trend following
- Reversals
- Sector strength

Typical holding period:

- Several days to several weeks

### 3.3 Position Trading

Focus:

- Daily
- Weekly
- Technical and fundamental combination
- Multi-week to multi-month holding periods

### 3.4 Long-Term Investing

Focus:

- Fundamentals
- Revenue growth
- Earnings growth
- Free cash flow
- Debt
- Margins
- ROE / ROIC
- Valuation
- Competitive strength
- Dividend quality
- Long-term trends

Holding period:

- Months to years

---

## 4. Portfolio Builder

DarkSage will include a portfolio builder.

Inputs may include:

- Starting capital
- Monthly contribution
- Risk tolerance
- Time horizon
- Number of holdings
- Allowed asset types
- Sector limits
- Maximum position size
- Growth vs income preference

Portfolio profiles may include:

- Aggressive Growth
- Balanced Growth
- Conservative
- Income
- Custom

Portfolio analytics should include:

- Diversification
- Sector concentration
- Correlation
- Factor exposure
- Volatility
- Drawdown
- Beta
- Risk-adjusted return
- Benchmark comparison

---

## 5. Market Scanner

The scanner must analyze the stock universe using deterministic calculations before involving AI.

Core indicators include:

- SMA
- EMA
- RSI
- MACD
- ATR
- Bollinger Bands
- VWAP
- ADX
- OBV
- Relative volume
- Relative strength

Scanner presets may include:

- Momentum Movers
- Breakout Candidates
- Mean Reversion
- Oversold Quality Stocks
- Trend Leaders
- Value Opportunities
- Earnings Setups
- Day Trade Candidates
- Swing Opportunities
- Long-Term Investments

---

## 6. Strategy Engine

Supported strategy families should include:

- Momentum
- Breakout
- Reversal
- Mean reversion
- Trend following
- Swing
- Scalping
- Pairs trading
- Sector rotation
- Event-driven

Options strategies may be added later.

Each strategy must use a StrategyProfile containing:

- Rules
- Indicators
- Entry logic
- Exit logic
- Stop logic
- Risk rules
- Supported timeframes
- Supported instruments
- Historical statistics
- Version
- Status

Strategy statuses:

- Experimental
- Watch
- Active
- Reduced
- Suspended

---

## 7. Strategy Performance Intelligence

DarkSage must track more than simple win rate.

Metrics include:

- Wins
- Losses
- Win rate
- Average win
- Average loss
- Profit factor
- Expectancy
- Max drawdown
- Sharpe ratio
- Sortino ratio
- Average holding time
- Trade count
- Sample-size confidence

Performance must be tracked by:

- Strategy
- Stock
- Sector
- Timeframe
- Market regime
- Instrument type
- Time of day
- Day of week
- Entry type
- Exit type

---

## 8. Strategy DNA

Each stock should develop a Strategy DNA profile.

Example characteristics:

- Best-performing strategies
- Worst-performing strategies
- Best timeframe
- Best market regime
- Typical volatility
- Trend persistence
- Mean-reversion tendency
- Event sensitivity
- Best holding period
- Preferred entry behavior

Strategy DNA must be based on statistical evidence, not AI guessing.

---

## 9. Backtesting

Backtesting is a core system.

Must support:

- Historical backtests
- Out-of-sample testing
- Walk-forward testing
- Parameter stability testing
- Monte Carlo simulation
- Replay mode
- Strategy A/B testing
- Strategy tournament mode
- Benchmark comparison

Backtests must account for:

- Slippage
- Fees
- Spread
- Liquidity
- Partial fills where applicable
- Corporate actions
- Point-in-time data
- Look-ahead bias
- Survivorship bias

---

## 10. Anti-Overfitting Safeguards

DarkSage must include:

- Minimum sample-size requirements
- Multiple-testing protection
- False-discovery warnings
- Parameter stability analysis
- Out-of-sample validation
- Walk-forward validation
- Paper forward testing

No strategy may be promoted solely because of an impressive in-sample backtest.

---

## 11. Shadow Trading

DarkSage should support internal shadow trades.

Shadow trades:

- Do not place broker orders
- Simulate alternate strategies
- Simulate alternate entry methods
- Simulate alternate exits
- Compare instrument choices
- Generate additional learning data

---

## 12. Strategy Promotion Pipeline

Strategies should progress through:

1. Backtest
2. Validation
3. Out-of-sample
4. Shadow testing
5. Paper auto-trading
6. Limited live trading
7. Approved live trading

Strategies may be automatically demoted if performance deteriorates.

---

## 13. Market Regime Engine

DarkSage should identify environments such as:

- Bull trend
- Bear trend
- Sideways
- High volatility
- Low volatility
- Risk-on
- Risk-off
- Growth accelerating
- Growth slowing
- Inflation rising
- Inflation falling
- Rates rising
- Rates falling

Strategy performance should be tracked by regime.

---

## 14. Chart System

DarkSage should support two chart renderers:

1. Apache ECharts
2. TradingView Lightweight Charts

Users may choose the chart engine.

The chart renderer must not own the strategy logic.

All chart engines must use the same:

- Market data
- Indicator calculations
- Pattern calculations
- Signal data
- Trade markers
- AI annotations

DarkSage owns the chart data and calculations.

The chart system should support:

- Candlesticks
- Volume
- Indicators
- Support/resistance
- Trendlines
- Fibonacci
- Pattern overlays
- Trade entries
- Stops
- Targets
- Backtest trades
- Paper/live trades
- User drawings
- AI drawings

---

## 15. Pattern Recognition

Patterns may include:

- Support/resistance
- Trendlines
- Breakouts
- Triangles
- Wedges
- Flags
- Head and shoulders
- Fibonacci levels

All detected patterns must include:

- Confidence
- Geometry
- Reasoning
- Historical performance where available

---

## 16. Signal System

Each signal should include:

- Symbol
- Company
- Direction
- Strategy
- Entry
- Stop
- Targets
- Risk/reward
- Confidence
- Quantitative score
- Technical score
- Fundamental score
- Sentiment score
- Detected patterns
- Indicators
- Reasoning
- Timestamp
- Expiration where applicable

Signals should receive grades such as:

- A+
- A
- B
- C
- D

---

## 17. Why-Trade / Why-Not-Trade Engine

Every accepted or rejected signal should explain the decision.

Examples of rejection reasons:

- Poor risk/reward
- Earnings risk
- Wide spread
- Low liquidity
- Weak strategy history
- Regime mismatch
- Sector concentration
- Stale data
- Excessive correlation
- Risk budget exhausted

---

## 18. Paper Auto-Trader

Initial execution mode is paper only.

Every trade passes through the canonical TradeValidationPipeline (ARCHITECTURE.md §14), repeated here exactly:

```
AI / Strategy Engine
→ Trade Proposal
→ Signal Validator
→ Strategy Validation
→ Risk Engine
→ Permissions Engine
→ Portfolio / Exposure Checks
→ Buying Power Checks
→ Market Condition Checks
→ Order Validation
→ Execution Engine
→ Broker Adapter
```

Once past the Broker Adapter (which resolves to the Paper Broker implementation in Phase 7), paper-specific post-trade stages follow:

1. Position Monitoring
2. Exit Logic
3. Trade Journal
4. Performance Update

---

## 19. Future Live Trading

Live trading is a future feature.

Requirements include:

- Separate live credentials
- Explicit unlock
- Max daily loss
- Max weekly loss
- Max position size
- Max strategy allocation
- Max sector exposure
- Max correlated exposure
- Kill switch
- Duplicate-order prevention
- Broker reconciliation
- Stale-data protection
- Data-quality checks
- API failure handling
- Trading-hours controls
- Audit logs

The application must never require withdrawal permissions.

---

## 20. Risk Engine

Risk controls include:

- Position sizing
- Risk per trade
- Portfolio risk budget
- Daily loss limit
- Weekly loss limit
- Strategy drawdown protection
- Correlated exposure
- Sector exposure
- Factor exposure
- Liquidity
- Spread
- Volatility
- Event risk

---

## 21. Strategy Tournament

DarkSage may run multiple simulated strategy accounts.

Example:

- Breakout
- Momentum
- Swing
- Trend Following
- Mean Reversion
- Combined Meta Strategy

All should operate under comparable risk assumptions.

Metrics:

- Return
- Drawdown
- Win rate
- Profit factor
- Sharpe
- Sortino
- Risk-adjusted return

---

## 22. Portfolio Research Features

Potential features include:

- What-if simulator
- Stress testing
- Rebalancing
- Contribution optimizer
- Dividend reinvestment simulation
- Goal probability
- Glide paths
- Thesis tracking
- Thesis-broken alerts
- Benchmark comparison
- Alpha attribution

---

## 23. AI Architecture

### AI Provider Abstraction

DarkSage must support multiple AI providers behind a single common interface, so providers can be added, replaced, or removed without rewriting business logic.

Initial supported providers:

- Local models (default)
- OpenAI
- Anthropic
- Google Gemini
- Custom OpenAI-compatible endpoints

Users configure cloud providers with their own API keys. DarkSage does not bundle, subsidize, or require cloud AI usage.

### Local AI

Default and preferred mode.

Uses local models for:

- Signal explanation
- Candidate review
- Pattern explanation
- Portfolio commentary
- Strategy summaries

Goal:

- No token cost for routine analysis
- The application must work fully with no cloud AI provider configured

### Cloud AI

Optional. User-configured, using the user's own API key.

Used for:

- Deep research
- Long-form analysis
- Complex reasoning
- Macro synthesis
- Earnings transcript analysis

Cloud AI must never be required for basic operation. Cloud AI must never be required for deterministic scanning, indicators, risk calculations, backtesting, portfolio math, or trade validation — these remain deterministic local code regardless of which AI providers are configured.

### Per-Feature Provider Selection

Users may independently select the provider and model used for each AI feature, including:

- Sage chat
- Deep signal analysis
- Research / news summaries
- Strategy explanations

Changing the provider/model for one feature must not affect the others. Configuration is authoritative in the backend, not the client.

### Credential Handling

See SECURITY_RULES.md for full requirements. Summary:

- API keys are never committed, logged, or exposed in frontend/client source.
- Production credentials use secure OS/application credential storage or an encrypted secrets vault, not plaintext, where avoidable.
- No AI provider may bypass or shortcut the canonical TradeValidationPipeline (Section 2.3; full definition ARCHITECTURE.md §14), regardless of which provider generated the proposal. No provider may directly access or call the Execution Engine or Broker Adapter.

---

## 24. AI Abstention

AI must be allowed to say:

- Insufficient confidence
- Conflicting evidence
- No trade
- More data required

The system should reward abstaining when there is no clear edge.

---

## 25. Strategy Discovery

DarkSage may search for new strategy combinations.

Discovered strategies must remain experimental until they pass:

- Out-of-sample validation
- Walk-forward validation
- Shadow testing
- Paper forward testing

No automatically discovered strategy may go directly live.

---

## 26. Data Quality

DarkSage must monitor:

- Missing candles
- Stale quotes
- Bad timestamps
- Invalid prices
- Suspicious volume
- Provider outages
- Corporate action adjustments

Trading must pause when critical data integrity is uncertain.

---

## 27. Audit Trail

Every trade decision should record:

- Timestamp
- Market-data snapshot
- Indicators
- Strategy version
- AI model/version
- AI output
- Risk decision
- Permission decision
- Order request
- Broker response
- Fill
- Exit
- Result

---

## 28. Security

Core rules:

- Never store credentials in source code
- Never commit secrets
- Use environment variables or OS credential storage
- Separate paper and live credentials
- Encrypt sensitive local settings
- Use least privilege
- No withdrawal permissions
- Tamper-resistant logs
- Validate external inputs

---

## 29. Desktop and Mobile Clients

DarkSage should support:

### Desktop
- Electron
- React
- TypeScript

### Mobile
- React Native
- iPhone first
- Android-ready later

Both clients connect to the same backend API.

The mobile app should support:

- Dashboard
- Signals
- Watchlists
- Charts
- Portfolio monitoring
- Sage AI chat
- Auto-Trader status
- Emergency stop
- Trade approvals
- Push notifications

The mobile app should not run full scanning, backtesting, or execution locally.

Auto-Trader state must live in the backend so the phone can stop Auto-Trade even if it was enabled from the desktop.

---

## 30. Backend Deployment Model

### Development

Backend runs locally on the developer PC.

Target hosting cost:

- $0/month

### Paper Testing

Backend may continue running locally.

### Future Live Trading

Critical backend services move to an always-on hosted server.

Heavy workloads may remain local:

- Local AI
- Large backtests
- Strategy discovery
- Historical analytics

Desktop and mobile remain clients of the same backend API.

---

## 31. Development Stack

Initial preferred stack:

Frontend:
- Electron
- React
- TypeScript

Mobile:
- React Native

Charts:
- Apache ECharts
- TradingView Lightweight Charts

Backend:
- Python
- FastAPI

Database:
- SQLite initially

AI:
- Local-first
- llama.cpp / compatible runtime
- Pluggable provider interface (OpenAI, Anthropic, Google Gemini, custom OpenAI-compatible endpoints, local)
- Optional cloud AI, user-supplied API keys

Source Control:
- GitHub

Primary Editor:
- Visual Studio Code

Development Orchestration:
- Local development tools (unspecified)

---

## 32. Initial Build Priority

Phase 1:

- Project foundation
- Core models
- Market-data interface
- Historical data ingestion
- Candle model
- Indicator engine
- Scanner
- Signal model
- Backtesting foundation
- Strategy performance database
- Desktop shell
- Mobile API contracts
- Chart adapter abstraction
- ECharts renderer
- TradingView Lightweight renderer
- Paper trading integration
- Risk-engine foundation

No live trading in Phase 1.
