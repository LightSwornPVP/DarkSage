# DarkSage Architecture

## 1. Purpose

This document defines the technical architecture for DarkSage.

DarkSage must remain modular so the desktop app, mobile app, backend, AI systems, strategy engine, data providers, chart engines, and broker integrations can evolve independently without requiring major rewrites.

## 2. High-Level Architecture

DarkSage uses a client/server architecture.

Clients:

- Desktop app
- Mobile app

Backend services:

- Market data
- Scanner
- Indicators
- Pattern recognition
- Strategy engine
- Backtesting
- Portfolio engine
- Risk engine
- Permissions engine
- Paper/live execution
- AI orchestration
- Notifications
- Audit logging

Flow:

Desktop App / Mobile App
→ DarkSage API
→ Core Backend Services
→ Market Data / Database / Broker / AI

The clients must never contain critical trading logic. Critical trading logic must live in the backend.

## 3. Desktop Application

Location: `apps/desktop/`

Stack:

- Electron
- React
- TypeScript

Responsibilities:

- Dashboard
- Scanner
- Signals
- Charts
- Strategy Lab
- Backtesting UI
- Portfolio UI
- Auto-Trader controls
- Settings
- Logs
- Research tools
- Sage AI interface

The desktop app is a client of the backend API and must not directly submit broker orders.

## 4. Mobile Application

Location: `apps/mobile/`

Preferred stack:

- React Native
- TypeScript

Initial target: iPhone  
Future target: Android

Responsibilities:

- Dashboard
- Signals
- Portfolio monitoring
- Charts
- Watchlists
- Notifications
- Sage AI interaction
- Auto-Trader status
- Emergency stop
- Trade approvals
- Strategy monitoring

The mobile app must not run the full scanner, backtester, or execution engine locally.

## 5. Backend

Location: `backend/`

Preferred stack:

- Python
- FastAPI

Core modules:

- `api/`
- `models/`
- `market_data/`
- `scanner/`
- `indicators/`
- `patterns/`
- `strategies/`
- `backtesting/`
- `portfolio/`
- `risk/`
- `permissions/`
- `execution/`
- `monitoring/`
- `notifications/`
- `database/`
- `audit/`
- `security/`

The backend is the source of truth for Auto-Trader state, orders, positions, portfolios, signals, strategies, risk state, and broker state.

## 6. Shared Models

Location: `shared/`

Shared models include:

- Candle
- Quote
- Signal
- StrategyProfile
- TradeDecision
- Position
- Portfolio
- MarketRegime
- RiskState
- Order
- BrokerState
- ChartAnnotation
- BacktestResult

## 7. Market Data Architecture

DarkSage must not be tightly coupled to one market-data provider.

Use provider adapters.

Example interface:

- `get_quote()`
- `get_candles()`
- `get_historical_candles()`
- `get_company_info()`
- `get_fundamentals()`
- `get_news()`
- `get_market_status()`

Flow:

Provider → Adapter → Normalizer → Cache / Database → Scanner / Charts / Backtester / Strategies

## 8. Indicator Engine

The same indicator engine must power:

- Charts
- Scanner
- Backtesting
- Strategies
- Paper Auto-Trader
- Future Live Auto-Trader

No duplicate indicator implementations.

Initial indicators:

- SMA
- EMA
- RSI
- MACD
- ATR
- Bollinger Bands
- VWAP
- ADX
- OBV
- Relative Volume
- Relative Strength

Indicators must be deterministic and unit tested.

## 9. Chart Architecture

Supported engines:

- Apache ECharts
- TradingView Lightweight Charts

Use a chart adapter abstraction.

Chart engines render data only. They must not independently calculate indicators or strategy logic.

## 10. Strategy Architecture

Strategies implement a common interface and each StrategyProfile includes:

- Unique ID
- Name
- Version
- Status
- Supported timeframes
- Supported instruments
- Configuration
- Risk assumptions
- Historical statistics

Statuses:

- Experimental
- Watch
- Active
- Reduced
- Suspended

## 11. Strategy Performance Architecture

Performance must be stored by:

- Strategy
- Strategy version
- Symbol
- Sector
- Timeframe
- Market regime
- Instrument
- Entry method
- Exit method
- Time of day
- Day of week

Metrics include:

- Trade count
- Wins
- Losses
- Win rate
- Expectancy
- Profit factor
- Average win
- Average loss
- Maximum drawdown
- Sharpe ratio
- Sortino ratio
- Confidence
- Sample size

## 12. Strategy DNA

Strategy DNA is generated from statistical performance data and must not be generated solely from AI opinion.

## 13. Backtesting Architecture

Backtesting should reuse production strategy logic whenever possible.

Components:

- Historical data loader
- Event engine
- Simulated broker
- Fill model
- Spread model
- Slippage model
- Fee model
- Portfolio accounting
- Risk engine
- Performance analytics

Backtests must protect against:

- Look-ahead bias
- Survivorship bias
- Future-known fundamentals
- Invalid fills
- Unrealistic liquidity assumptions
- Data leakage

## 14. Broker Architecture

Use a common broker interface.

Initial implementation:

- PaperBroker

Future:

- Live broker adapters

Required flow:

Strategy / AI → Trade Proposal → Signal Validator → Risk Engine → Permissions Engine → Portfolio Check → Execution Engine → BrokerAdapter

## 15. Auto-Trader Architecture

Auto-Trader state lives in the backend.

Possible states:

- disabled
- enabled
- paused
- emergency_stop

Desktop and mobile display the same backend state.

## 16. Emergency Controls

### Stop Trading

- Block all new orders
- Cancel pending entry orders
- Continue monitoring existing positions

### Emergency Flatten

- Block all new orders
- Cancel open orders
- Close active positions according to emergency execution rules

Emergency Flatten must require strong authentication in live mode.

## 17. Risk Engine

Checks include:

- Maximum risk per trade
- Maximum daily loss
- Maximum weekly loss
- Maximum position size
- Maximum number of open positions
- Sector concentration
- Correlated exposure
- Portfolio risk budget
- Strategy drawdown limits
- Liquidity
- Spread
- Volatility
- Market regime
- Event risk

AI cannot override the risk engine.

## 18. Permissions Engine

Controls what DarkSage may trade.

Instrument categories:

- Stocks
- ETFs
- Options
- Crypto
- Futures

Initial focus:

- Stocks
- ETFs where supported

No trade may bypass permissions.

## 19. Portfolio Architecture

Portfolio services manage:

- Holdings
- Cash
- Exposure
- Sector allocation
- Correlations
- Risk budgets
- Performance
- Benchmarks
- Rebalancing
- Goal tracking

## 20. Database

Initial database:

- SQLite

Future options:

- PostgreSQL
- TimescaleDB only if justified

Do not introduce infrastructure complexity until needed.

## 21. Caching

Initial approach:

- In-memory caching
- Local persistence

Do not add Redis until there is a demonstrated need.

## 22. AI Architecture

Location: `ai/`

Modules:

- `local/`
- `cloud/`
- `agents/`
- `orchestrator/`

AI is advisory and may not bypass deterministic safety systems.

## 23. Local AI

Local AI is the default for routine work.

Possible runtimes:

- llama.cpp-compatible runtimes
- ONNX
- other efficient local runtimes

## 24. Cloud AI

Cloud AI is optional and must never be required for basic DarkSage operation.

## 25. Notifications

Backend notification services should support:

- Desktop notifications
- Mobile push notifications
- Signal alerts
- Trade fills
- Stop/target events
- Risk warnings
- Auto-Trader pauses
- Strategy promotion/demotion
- Emergency events
- Data-feed failures

## 26. Mobile Control Security

Mobile must be able to:

- Pause Auto-Trade
- Trigger emergency stop
- Approve or reject trades when approval mode is enabled

High-risk actions should require strong authentication.

## 27. Deployment Stages

### Stage 1 — Local Development

Everything runs on the developer PC. Target hosting cost: $0/month.

### Stage 2 — Paper Testing

Backend may continue running locally.

### Stage 3 — Hosted Backend

Critical backend services move to an always-on server.

### Stage 4 — Live Trading

Requires hardened security, broker reconciliation, monitoring, fail-safe controls, kill switches, deployment review, audit logging, and live strategy promotion requirements.

## 28. Security Principles

- Never commit credentials
- Never hard-code API keys
- Use environment variables or secure credential storage
- Separate paper and live credentials
- Use least privilege
- Never require withdrawal permissions
- Validate external input
- Maintain audit logs
- Encrypt sensitive configuration where appropriate
- Fail closed when critical systems are uncertain

## 29. Development Environment

Primary editor:

- Visual Studio Code

Supporting IDE:

- Visual Studio 2026

Source control:

- GitHub

Development tooling:

- Local development tools (unspecified)

## 30. Core Architectural Rules

Never tightly couple:

- UI and trading logic
- Strategy logic and broker APIs
- Chart renderers and indicator calculations
- Market-data providers and core models
- AI providers and deterministic systems
- Desktop state and Auto-Trader state

Every major external dependency should be replaceable through an interface or adapter.

The backend is the authoritative source of truth for trading and account state.
