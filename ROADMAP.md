# DarkSage Development Roadmap

## Guiding Principles

- Build the smallest reliable core first.
- Paper trading only during development.
- Keep recurring costs as close to $0 as practical.
- Prefer deterministic local code over AI for calculations.
- Local AI first; cloud AI optional.
- Do not build advanced features before their foundations are stable.
- Every critical trading feature requires tests and review.

---

# Phase 0 — Foundation

Goal: establish a safe, consistent development environment.

- Repository structure
- PROJECT_SPEC.md
- ARCHITECTURE.md
- TRADING_RULES.md
- SECURITY_RULES.md
- AGENTS.md
- ROADMAP.md
- README.md
- .gitignore
- VS Code setup
- Git/GitHub setup
- Local development tooling setup (tool-neutral)
- Branch and PR conventions
- CI foundation
- Secret scanning foundation

Exit criteria:

- Documentation committed
- Development environment reproducible
- Agents follow repository rules
- No secrets committed

---

# Phase 1 — Core Market Intelligence

Goal: create the first working DarkSage desktop research application.

Backend:

- FastAPI application skeleton
- SQLite database
- Configuration system
- Core models
- Candle model
- Quote model
- Signal model
- StrategyProfile model
- TradeDecision model
- Provider adapter interfaces
- Historical data ingestion
- Data normalization

Quant:

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
- Unit tests against known reference data

Scanner:

- Initial stock universe
- S&P 500-focused scanner
- Ranking/scoring pipeline
- Scanner presets
- Candidate filtering

Desktop:

- Electron + React + TypeScript shell
- Navigation
- Dashboard
- Scanner page
- Signal list
- Signal detail

Charts:

- ChartAdapter interface
- Apache ECharts implementation
- TradingView Lightweight Charts implementation
- User-selectable chart engine
- Candles
- Volume
- Basic indicators

Exit criteria:

- Desktop app launches
- Backend starts locally
- Market data can be loaded
- Indicators match reference tests
- Scanner ranks candidates
- Both chart engines render the same data

---

# Phase 2 — Backtesting and Strategy Lab

Goal: prove strategy logic historically before paper automation.

- Strategy interface
- Initial strategy families:
  - Momentum
  - Breakout
  - Mean reversion
  - Reversal
  - Trend following
- Backtest event engine
- Simulated broker
- Fill model
- Spread model
- Slippage model
- Fee model
- Portfolio accounting
- Benchmark comparison
- Win/loss tracking
- Expectancy
- Profit factor
- Max drawdown
- Sharpe
- Sortino
- Trade count
- Sample-size confidence
- Out-of-sample testing
- Walk-forward framework
- Parameter stability
- Replay mode foundation
- A/B strategy tests
- Strategy versioning

Exit criteria:

- Strategies can be reproduced deterministically
- Backtests include realistic costs
- No look-ahead leakage in validation tests
- Results are segmented by stock/timeframe/regime where supported

---

# Phase 3 — Strategy Intelligence

Goal: learn which strategies work best under which conditions.

- Strategy performance database
- Strategy × stock analysis
- Strategy × sector analysis
- Strategy × timeframe analysis
- Strategy × regime analysis
- Entry-method analysis
- Exit-method analysis
- Time-of-day analysis
- Day-of-week analysis
- Strategy DNA
- Market regime classification
- Strategy ranking
- Confidence calibration
- False-discovery protection
- Multiple-testing warnings
- Performance decay detection
- Strategy promotion/demotion
- Strategy families
- Strategy correlation
- Strategy ensemble voting
- Meta-strategy selection
- Statistical validation of all strategies and patterns regardless of origin — including educational-source concepts (Trading Knowledge Engine, PROJECT_SPEC.md §33) — globally and per stock/sector/timeframe/regime/confluence

Exit criteria:

- DarkSage can explain why one strategy is favored over another
- Small samples are appropriately down-weighted
- Strategy performance changes are detected over time

---

# Phase 4 — Portfolio Builder

Goal: add long-term investing and portfolio intelligence.

- Portfolio models
- Multiple paper portfolios
- Portfolio Builder
- Aggressive Growth profile
- Balanced Growth profile
- Conservative profile
- Income profile
- Custom profile
- Sector exposure
- Correlation
- Factor exposure
- Risk budget
- What-if simulator
- Stress tests
- Rebalancing
- Contribution optimizer
- Benchmark comparison
- Goal planning
- Goal probability
- Dividend reinvestment simulation
- Thesis tracking
- Thesis-broken alerts
- Alpha attribution

Exit criteria:

- Users can create and compare paper portfolios
- Portfolio risks are visible and explainable
- Benchmark comparison is included

---

# Phase 5 — Pattern Recognition, Advanced Charts, and Trading Knowledge Engine

Goal: add visual technical intelligence, and the ability to learn, structure, retrieve, explain, detect, test, and validate trading concepts from user-provided educational material (see PROJECT_SPEC.md §33, ARCHITECTURE.md §31).

- Support/resistance
- Trendlines
- Breakouts
- Triangles, Wedges (Rising/Falling), Flags (Bullish/Bearish), Symmetrical Triangles (Bullish/Bearish)
- Double/Triple Top and Bottom
- Head and Shoulders / Inverse Head and Shoulders
- Fibonacci
- Candlestick anatomy, individual and multi-candle candlestick patterns, extensible pattern definitions
- Knowledge Engine ingestion of user-provided educational material with provenance metadata (source, date, category, confidence, staleness, verification-required)
- Contextual setup-quality scoring (trend, regime, support/resistance, volume, relative volume, volatility, momentum, multi-timeframe confirmation, sector context, liquidity, nearby invalidation, risk/reward, historical performance, Strategy DNA, confluence)
- Explicit separation of pattern detection, setup quality, and trade eligibility — a detected pattern is never automatically a trade
- Trading Education mode: concept explanations, chart examples, interactive pattern walkthroughs, quizzes, historical replay, why-trade/why-not-trade, comparative historical setups
- AI annotations
- Entry/stop/target overlays
- Backtest trade overlays
- User drawings
- AI drawings
- Multi-timeframe views
- Pattern confidence
- Pattern historical performance
- Why-trade / why-not-trade explanations

Exit criteria:

- Patterns are structured data, not just visual guesses
- Both chart engines can render DarkSage annotations
- Pattern detection, setup-quality scoring, and trade eligibility are implemented as distinct, non-conflatable steps
- Educational-source concepts carry provenance metadata and are never presented as current authoritative fact without verification
- Knowledge Engine ingestion, scoring, and statistical validation run as deterministic local code with no cloud AI dependency; AI involvement is limited to explanation, retrieval, tutoring, and summarization

---

# Phase 6 — Local AI, Cloud Providers, and Sage

Goal: add low-cost AI assistance without making AI authoritative, and let users optionally bring their own cloud AI providers.

During Phase 6, all AI output — local or any configured cloud provider — is research/display/advisory only: chat responses, signal explanations, candidate review, portfolio commentary, strategy summaries. AI cannot produce an executable broker order and cannot bypass any deterministic control. Executable trade proposals remain disabled in this phase regardless of AI confidence or user request, until the full canonical TradeValidationPipeline (ARCHITECTURE.md §14) exists, is implemented, and is approved — see Phase 7.

- Local model manager
- Hardware detection
- llama.cpp-compatible runtime
- AI provider abstraction/interface (common `complete()`/`chat()`/`stream()` contract)
- OpenAI provider adapter
- Anthropic provider adapter
- Google Gemini provider adapter
- Custom OpenAI-compatible endpoint adapter
- Per-feature provider/model selection (Sage chat, deep signal analysis, research/news summaries, strategy explanations)
- Secure credential storage (OS credential store / encrypted vault) for provider API keys
- Settings > AI Providers UI (add, test, edit, disable, remove provider credentials)
- Model selection
- Sage chat
- Signal explanations
- Candidate review
- Counterargument engine
- Portfolio commentary
- Strategy summaries
- Trading Education mode tutoring (concept explanations, quizzes, why-trade/why-not-trade) — advisory only, never replaces deterministic detection or scoring in the Knowledge Engine
- AI abstention
- Confidence-source separation
- Cloud AI cost controls
- Model comparison metrics

Exit criteria:

- Core app works with zero cloud AI providers configured
- A cloud provider (OpenAI, Anthropic, Gemini, or custom endpoint) can be added or swapped per feature without changing feature code
- Deterministic scanning, indicators, risk calculations, backtesting, portfolio math, and trade validation never depend on cloud AI
- AI cannot bypass deterministic rules, regardless of which provider is configured
- AI output is validated before use
- No provider API key ever appears in commits, logs, or frontend/client source

---

# Phase 7 — Paper Auto-Trader

Goal: automatically execute approved strategies in paper mode.

- Paper broker integration
- Execution engine
- Risk engine
- Permissions engine
- Portfolio checks
- Order validation
- Unique/idempotent order IDs
- Position monitoring
- Stop/target handling
- Daily loss limits
- Weekly loss limits
- Strategy drawdown controls
- Correlated exposure checks
- Sector exposure checks
- Event-risk checks
- Emergency Stop
- Emergency Flatten simulation
- Trade journal
- Audit trail
- Broker reconciliation
- Fault injection

Exit criteria:

- No live trading exists
- Full canonical TradeValidationPipeline (ARCHITECTURE.md §14) is implemented and independently reviewed before any executable trade proposal is enabled
- Duplicate-order tests pass
- Risk engine cannot be bypassed
- Emergency Stop passes tests
- Paper account reconciles correctly

---

# Phase 8 — Shadow Trading and Strategy Tournament

Goal: improve strategies without risking capital.

- Shadow trades
- Alternate entries
- Alternate exits
- Alternate sizing
- Strategy tournament accounts
- Champion vs Challenger
- Digital twin foundation
- Monte Carlo simulation
- Risk-of-ruin analysis
- Dynamic position sizing research
- Strategy capacity research

Exit criteria:

- Shadow results are separate from broker trades
- Strategy promotion uses evidence, not only backtests

---

# Phase 9 — Mobile App

Goal: make DarkSage controllable and useful from iPhone.

- React Native shell
- Authentication
- Dashboard
- Signals
- Watchlists
- Charts
- Portfolio monitoring
- Sage chat
- Push notifications
- Auto-Trader status
- Emergency Stop
- Trade approvals
- Strong authentication for high-risk actions
- Offline cached read-only snapshots
- Secure storage
- Android-ready architecture

Exit criteria:

- Mobile sees the same backend state as desktop
- Mobile can stop paper Auto-Trader
- Critical actions are backend-authorized

---

# Phase 10 — Advanced Research

Goal: add deeper market and portfolio intelligence.

- Earnings intelligence
- News relevance filtering
- Event calendar
- Earnings transcript analysis
- Fundamental change detection
- Insider/institutional context where data permits
- Sector rotation
- Market breadth
- Economic regime engine
- Regime transition detection
- Historical analog search
- Scenario distributions
- Market anomaly detection
- Natural-language scanner builder
- Custom strategy builder
- Strategy discovery engine

Exit criteria:

- Research features are explainable
- Strategy discovery cannot promote directly to live

---

# Phase 11 — Options Research

Goal: add options safely as a separate instrument system.

- Options data adapter
- Options chain
- Greeks
- IV rank / percentile
- Volatility surface
- Options backtesting
- Assignment/exercise simulation
- Earnings IV-crush simulation
- Payoff visualizer
- Strategy selector
- Defined-risk strategies first

No live options trading in this phase.

---

# Phase 12 — Production Hardening

Goal: prepare the backend for always-on deployment.

- PostgreSQL evaluation/migration if justified
- Always-on backend deployment
- Secure secret management
- HTTPS/TLS
- Authentication hardening
- Authorization roles
- Session management
- Rate limiting
- Monitoring
- Backups
- Recovery procedures
- Tamper-evident audit logs
- Data health monitoring
- Broker reconciliation hardening
- Deployment rollback
- Security review

Exit criteria:

- Backend can run independently of desktop
- Mobile can control backend while desktop is off
- Production failure modes are tested

---

# Phase 13 — Limited Live Trading

Goal: transition only proven strategies to very small real-money allocations.

Prerequisites:

- Independent security review
- Independent trading-safety review
- Paper results acceptable
- Live broker adapter reviewed
- Reconciliation verified
- Kill switch verified
- Duplicate-order prevention verified
- Data health verified
- Explicit user unlock

Progression:

1. Very small allocation
2. Small allocation
3. Moderate allocation
4. Approved allocation

Strategies may be demoted automatically based on predefined rules.

---

# Phase 14 — Full Live Platform

Goal: mature production trading platform.

- Manual mode
- Approval-required mode
- Semi-auto mode
- Full-auto mode for approved strategies
- Live execution analytics
- Slippage analytics
- Order-type intelligence
- Digital twin comparison
- Live vs paper vs backtest comparison
- Strategy decay monitoring
- Canary deployments
- Advanced notifications
- Tax-aware features where appropriate
- Additional broker adapters where justified

Live trading remains subject to deterministic risk and permissions systems at all times.
