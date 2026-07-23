# DarkSage Agent Rules

## Purpose

This document defines how contributors and development tooling must work inside the DarkSage repository.

These rules apply to all contributors and any automated development tooling, present or future.

## Source of Truth

Before making changes, agents must read:

- PROJECT_SPEC.md
- ARCHITECTURE.md
- ROADMAP.md
- AGENTS.md
- SECURITY_RULES.md
- TRADING_RULES.md

Priority order when documents conflict:

1. SECURITY_RULES.md
2. TRADING_RULES.md
3. ARCHITECTURE.md
4. PROJECT_SPEC.md
5. ROADMAP.md
6. AGENTS.md

Security and trading safety always take priority.

This priority order is fixed and formal. Any local, tool-specific, or machine-local development-tool configuration (tracked or untracked) is a convenience summary only — it never overrides this order or any of the six documents above, and it never becomes authoritative project governance by virtue of a development tool reading it automatically.

## Scope Control

Agents must not invent major architectural changes without explicit approval.

Without approval, agents must not:

- Replace core frameworks
- Change broker architecture
- Change database strategy
- Remove safety systems
- Add live trading
- Add paid dependencies
- Add unnecessary cloud infrastructure
- Rewrite major modules without justification

## Cheap-First Development

Prefer:

1. Deterministic local code
2. Open-source libraries
3. Local AI
4. Free API tiers
5. Paid services only when justified

Do not introduce recurring paid services without explicit approval.

## Paper Trading Only During Development

No development agent may enable real-money trading.

Execution work must target simulation, shadow trading, or paper trading until a future explicitly approved live phase.

## Branching

Avoid major feature changes directly on `main`.

Use focused feature branches, for example:

- `feature/backend-foundation`
- `feature/indicator-engine`
- `feature/chart-adapter`
- `feature/backtesting-core`
- `feature/mobile-shell`
- `fix/order-idempotency`

## Pull Requests

Major changes should be reviewed before merging.

A pull request should include:

- Summary
- Files changed
- Why the change was made
- Tests added
- Risks
- Known limitations
- Follow-up work

## Specialist Ownership

### Architect Agent

Owns:

- System architecture
- Cross-module interfaces
- Design reviews
- Major refactors
- Dependency decisions

### Frontend Agent

Owns:

- `apps/desktop/`
- React
- TypeScript
- Electron
- Apache ECharts
- TradingView Lightweight Charts
- Desktop UX

Must not implement broker execution logic.

### Mobile Agent

Owns:

- `apps/mobile/`
- React Native
- iPhone UI
- Notifications UI
- Auto-Trader controls
- Mobile charts

Must not move critical trading logic into the phone app.

### Backend Agent

Owns:

- `backend/app/api/`
- `backend/app/models/`
- `backend/app/database/`
- Backend infrastructure
- FastAPI
- Persistence
- Service orchestration
- Authentication foundations

### Quant Agent

Owns:

- Indicators
- Scanner
- Strategies
- Backtesting
- Strategy statistics
- Strategy DNA
- Regime analysis
- Trading Knowledge Engine (`backend/app/knowledge/`): candlestick/chart-pattern detection, contextual scoring, statistical concept validation

Must protect against look-ahead bias, survivorship bias, data leakage, overfitting, and invalid statistics.

A detected pattern or scored setup is never itself a trade signal — trade eligibility is decided only by the canonical TradeValidationPipeline (ARCHITECTURE.md §14).

### Trading Agent

Owns:

- Risk
- Permissions
- Execution
- Monitoring
- Broker adapters

Must not bypass safety layers and must not solely approve its own critical trading-safety code.

### AI Agent

Owns:

- `ai/local/`
- `ai/cloud/`
- `ai/providers/`
- `ai/agents/`
- `ai/orchestrator/`

AI functionality remains advisory.

Provider adapters (OpenAI, Anthropic, Google Gemini, custom OpenAI-compatible endpoints, local) must implement the common provider interface and must never handle broker credentials, submit broker orders, or bypass the risk/permissions pipeline. The AI Agent is responsible for ensuring provider API keys are never logged, committed, or exposed in frontend source.

The AI Agent also provides the natural-language layer for Trading Education mode (explanations, tutoring, semantic retrieval, concept comparison) but does not own pattern/candlestick detection, contextual scoring, or statistical concept validation — those are deterministic and owned by the Quant Agent (`backend/app/knowledge/`, `patterns/`, `indicators/`). AI must never replace a deterministic calculation when one already exists.

### QA Agent

Owns:

- Tests
- Automated validation
- Regression testing
- Integration testing
- Fault injection
- Edge cases

The QA agent should actively try to break the system.

### Security Reviewer

Reviews:

- Secret handling
- Authentication
- Authorization
- Broker credential safety
- API exposure
- Dependency security
- Live-trading safeguards

## File Ownership Boundaries

Avoid unrelated edits.

Cross-boundary changes require coordination.

## Shared Contracts

Changes to shared models or API contracts must update all affected clients, backend services, tests, and migration notes.

## No Duplicate Business Logic

Do not calculate the same trading logic independently in multiple places.

The same indicator, risk, strategy, and performance logic should have one authoritative implementation.

## Testing

Every meaningful feature must include tests where practical.

Critical areas require strong coverage:

- Indicators
- Backtesting
- Risk engine
- Permissions
- Order execution
- Broker adapters
- Authentication
- Portfolio accounting
- Strategy statistics

Use unit, integration, regression, fault-injection, and end-to-end tests where useful.

## No Silent Strategy Changes

Every trading strategy must be versioned.

If strategy logic changes:

- Increment version
- Record changes
- Preserve prior results
- Re-run validation

## Database Changes

Use migrations once migrations are introduced.

Destructive schema changes require impact review and a migration/backup path.

## Dependencies

Before adding a dependency, evaluate:

- Necessity
- Maintenance
- Security
- Cost
- Standard-library alternatives
- Deployment complexity

Avoid dependency bloat.

## External Services

Do not automatically add:

- Paid APIs
- Cloud databases
- Hosted Redis
- Paid charting
- Cloud GPUs
- Subscription services

without explicit approval.

User-configured cloud AI providers (OpenAI, Anthropic, Google Gemini, custom OpenAI-compatible endpoints) are an exception: users may opt in and supply their own API key for their own usage. This is not DarkSage adding a recurring paid service — local AI must remain the default, no provider may be pre-selected or required, and no install may silently default to a cloud provider or ship a bundled/shared API key.

## Command Approval Policy

Routine, non-destructive repository operations should proceed without requesting approval each time.

Pre-approved, safe to run without asking:

- `git status`
- `git diff`
- `git diff --check`
- `git log`
- `git grep`
- `git ls-files`
- `git check-ignore`
- Reading files
- Listing directories
- Running project-local tests
- Running linters
- Running formatting checks
- Running verification scripts
- Checking installed tool versions
- Checking whether commands/tools exist
- Creating temporary test files that are automatically restored or deleted
- Negative tests that intentionally verify a validation script fails correctly, provided the original file is restored automatically
- Read-only network fetches to official upstream documentation or repositories, when needed to verify versions, SHAs, schemas, or configuration

Do not repeatedly request approval for substantially similar safe commands. Batch related safe checks together instead of prompting separately for each one.

Explicit approval is still required before:

- Deleting or permanently overwriting user data
- Destructive git operations
- Force pushes
- History rewrites
- Hard resets
- Deleting branches containing unmerged work
- Installing or removing system-wide software
- Modifying system settings
- Changing credentials or secrets
- Publishing releases
- Merging pull requests
- Pushing directly to protected branches
- Sending external communications
- Making purchases or enabling paid services
- Enabling live trading
- Placing real-money trades
- Connecting real-money broker execution
- Emergency Flatten actions on a live account
- Any other irreversible or materially risky action

When uncertain, distinguish:

1. Routine, reversible development operations — proceed.
2. Destructive, external, financial, credential-related, live-trading, or irreversible operations — request approval.

## Documentation

Major features should update documentation.

Documentation should describe current behavior, not imaginary behavior.

## Code Quality

Prioritize:

- Clarity
- Maintainability
- Type safety
- Testability
- Explicit behavior
- Small modules
- Clear interfaces

Avoid clever code when simple code is safer.

## Error Handling

Critical errors must not be silently ignored.

Trading systems should fail closed.

## AI-Assisted Code Review

Generated code must be reviewed like human-written code.

Never assume AI-assisted code is correct.

## Critical Code Review

Independent review required for:

- Risk engine
- Permissions engine
- Execution engine
- Broker adapters
- Emergency Stop
- Emergency Flatten
- Authentication
- Authorization
- Credential storage
- Broker reconciliation
- Duplicate-order protection

## Commit Guidelines

Use clear focused commits.

Examples:

- `feat: add candle data model`
- `feat: implement RSI indicator`
- `test: add RSI reference tests`
- `fix: prevent duplicate paper orders`

Avoid vague messages.

## Research Separation

Experimental work must not silently affect production behavior.

Use experimental statuses, feature flags, shadow testing, and paper environments.

## Mobile / Backend Rule

The mobile app is a client.

It must not independently run the core Auto-Trader, store authoritative trading state, or submit broker orders directly.

## Desktop / Backend Rule

The desktop app is also a client.

Backend state is authoritative.

## Chart Rule

Chart libraries are renderers only.

They must not own strategy calculations, indicator truth, or trade logic.

## Provider Independence

Market-data providers and broker providers must use adapters.

Provider-specific logic must not leak into core systems.

## Feature Flags

High-risk or unfinished functionality should use feature flags.

Examples:

- Experimental strategies
- Cloud AI
- Options
- Live trading

Live trading defaults to disabled.

## Definition of Done

A task is not complete until:

- Code works
- Tests pass
- Errors are handled
- Documentation is updated where needed
- Security implications are considered
- Architecture rules are followed

Agents are builders, not project owners.

When uncertain, stop, explain the conflict, and request approval.
