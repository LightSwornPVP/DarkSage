# DarkSage Complete Features

| Field | Value |
|---|---|
| Document | DarkSage Complete Features (Master Catalog) |
| Version | 0.1.0 |
| Status | Draft (Foundation Pass) |
| Owner | TheSinnerMan |
| Owning Volume | DS-022 (`docs/codex/Volume-22-ProductExperience/`) |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

This is the **human-readable master feature catalog** for DarkSage. The machine-readable source of truth is `FEATURE_REGISTRY.csv` (268 features as of the 2026-07-26 audit repair pass); this document narrates and organizes that registry — it does not duplicate every field of every row. When this document and the registry ever appear to disagree, **the registry is authoritative** (the same source-of-truth rule the Core Codex already applies between Markdown and generated publications).

## How to Use This Document

- Each of the 32 categories below is in **dependency order** (a category generally depends on the ones before it).
- Every feature named here has a `feature_id` (format `FEAT-NNNN`) resolvable in `FEATURE_REGISTRY.csv`, where its full status, evidence, ownership, and timeline fields live.
- See `FEATURE_STATUS_DEFINITIONS.md` for what each status/classification value means.
- See `FEATURE_GOVERNANCE.md` for ownership rules and the controlled-ID family registry (including how naming collisions with existing DS-002/DS-007 families were resolved).
- See `TRADINGVIEW_CAPABILITY_COMPARISON.md` for the full TradingView-capability classification (A–E).
- See `RELEASE_STAGE_MATRIX.csv` and `FEATURE_TIMELINE.md` for stage definitions and nonbinding timeline ranges.
- See `PLATFORM_CAPABILITY_MATRIX.csv` and `EDITION_CAPABILITY_MATRIX.csv` for the full per-feature platform/edition grids.
- See `FEATURE_DEPENDENCIES.csv` for the feature-to-feature dependency graph.

## Scope of This Pass

This catalog covers: (1) core DarkSage features already documented in DS-001–DS-014; (2) product-expansion features for DS-015–DS-023; (3) TradingView-like capabilities required for initial release; (4) TradingView-like capabilities deferred but requiring groundwork now; (5) long-term ecosystem features in a controlled backlog; (6) explicitly rejected capabilities. **The Core Codex (DS-001–DS-014) itself is unchanged** — this catalog only organizes and cross-references it alongside the new expansion volumes.

---

## 1. Product Foundation

The structural bedrock everything else depends on: the Founder/Customer edition boundary (DS-015), the repository build-exclusion mechanism, and the deterministic execution authority (TradeValidationPipeline, ADR-002) every other feature answers to — **`Designed`, not `Implemented`** (2026-07-26 audit repair: no live TradeValidationPipeline/Risk Engine code exists yet; the prior `Implemented` claim cited backtesting-simulation code that explicitly disclaims being the real execution path). 4 features (FEAT-0001–0004). The Complete Features System itself (this document and its siblings) is cataloged here as a governance feature.

## 2. User Accounts and Onboarding

Account creation/authentication, first-run onboarding, MFA, and device trust. 4 features (registry `category = "02 User accounts and onboarding"`). Owned primarily by DS-002 (account requirements) and DS-021 (MFA/device trust).

## 3. Market Data

The provider-abstraction and ingestion layer. **This is the most mature category in the registry** — real-time/historical quote retrieval and U.S. stocks/ETFs coverage are already `Tested`/`In Development` with real evidence (`backend/app/market_data`, `tests/test_market_data_*.py`). The asset-class roadmap (crypto, futures, forex, international equities, bonds, macro, on-chain) is captured here too, all correctly deferred with explicit groundwork tags. 11 features. Owned by DS-002, supported by DS-004/DS-005.

## 4. Charts and Drawings

28 features spanning core charting (candlesticks, indicator panes — required for initial release) through the full TradingView-style drawing-tool and multi-chart-layout backlog (see `TRADINGVIEW_CAPABILITY_COMPARISON.md`'s Charting and Drawing Tools sections for the complete classification). Owned by DS-002/DS-022, with drawing-persistence and multi-chart-layout groundwork flagged `Groundwork Required Now`.

## 5. Watchlists

10 features: multiple/smart watchlists are initial-release requirements; grouping, color labels, badges, and broker sync are backlog. Owned by DS-002 (new DS-WCH family, reassigned from DS-022 in the 2026-07-26 audit repair -- normative watchlist behavior, not a UX-only concern); DS-022 supports watchlist UX/interaction.

## 6. Screeners

12 features. Stock/ETF screeners with technical and fundamental filters are initial-release requirements; the options screener is `Blocked` pending options-data-provider selection (shared blocker with the Options category). Owned by DS-002 (new DS-SCR family, reassigned from DS-022 in the 2026-07-26 audit repair) — **see `FEATURE_GOVERNANCE.md` §3 for the resolved DS-SCR (user-configurable screeners) vs. DS-SCN (automated scanner/watchtower) boundary: both owned by DS-002, no overlapping authority.** DS-022 supports screener UX/interaction only.

## 7. Alerts and Notifications

18 features. Price/indicator/strategy/portfolio/risk alerts, cooldowns, history, and multi-channel delivery are all initial-release requirements. Discord remains explicitly notification-only (carried forward unchanged from DS-ALT-004/DS-INT-006). Signed generic webhooks are groundwork-tracked as a future capability. Owned by DS-002 (existing DS-ALT family, reused).

## 8. Research and News

34 features — the largest category, combining news/sentiment, the full market-calendar set, and market-visualization heatmaps/breadth tools (all groundwork-tracked, `Stage 6` or later). Symbol/portfolio news, earnings calendar, and market-holiday/early-close calendars are initial-release requirements. Owned by DS-002, including the new DS-VIZ (Market Visualization) and DS-CAL (Market Calendars) families (reassigned from DS-022 stewardship in the 2026-07-26 audit repair -- both encode normative market data, not UX); DS-022 supports the visual/interaction layer only.

## 9. Sage Intelligence

9 features covering Founder Local Sage (permanently private, desktop/workstation-only runtime -- never a web/iOS/Android runtime), Customer Cloud Sage, the shared ADR-002/ADR-006 bounded-agency contract (`Designed`, not yet `Implemented` -- no Sage backend module exists yet), model routing, "why not this trade?", quotas, and honest failure-mode behavior. Owned by DS-018 (new), with DS-003 as the immutable behavioral authority.

## 10. Strategies and Indicators

10 features: the restricted DarkSage strategy language, visual/indicator builders, Founder-only Python research extensions (Founder-private workstation/development environment only), versioning, and mandatory safety scanning — all explicitly gated so **no customer-authored code ever enters the deterministic execution path** (the invariant is `Designed` per ADR-002; no live enforcement code exists yet -- see FEAT-0139/FEAT-0140). Owned by DS-002 (existing DS-STR family, reused).

## 11. Backtesting, Replay, and Simulation

6 features, and the **most evidence-rich category in the registry**: the backtesting engine, metrics, comparison, robustness analysis, and historical replay are `Tested` today, backed by real test files (`tests/test_backtest_*.py`, `tests/test_phase1_integration.py`, `tests/test_phase2_integration.py`). Paper trading (FEAT-0146, "basic backtesting integration") is `Planned`, not `Tested` (2026-07-26 second audit repair): no dedicated paper-trading position/order/portfolio integration code exists yet -- `backend/app/backtesting` is simulation-only, and `tests/test_phase2_integration.py::test_no_broker_or_live_execution_surface_exists` explicitly asserts that no live/paper execution surface exists. Owned by DS-002.

## 12. Trade Proposals

3 features: trade proposal generation and the canonical Trade Intelligence Package (already-approved architecture, DS-SIG-005/DS-SCA-029). Owned by DS-002.

## 13. Risk and Position Sizing

4 features anchored on the Deterministic Risk Engine. Risk-based position sizing and portfolio exposure checks are initial-release requirements. Owned by DS-002.

## 14. Stop Loss and Take Profit

**37 features — the single largest and most safety-critical category**, owned by the new DS-EXT family (DS-020). Covers every stop/target type (fixed, percentage, ATR/volatility, trailing, break-even, time-based, multi-target), broker-native brackets/OCO, DarkSage-managed protection where brokers lack native support, gap/slippage/partial-fill/cancel-replace handling, mobile stop/target editing, emergency close, exits-only mode, and the full kill-switch hierarchy (global/account/broker/strategy). **Automated entries require an approved deterministic exit plan; Sage may recommend one but never approves or bypasses its validation** (see the "Approved deterministic exit plan requirement" entry). Nearly all of this category is `initial_release_required = Yes` — see `FEATURE_REGISTRY.csv` filtered on `category = "14 Stop loss and take profit"` for the complete list.

## 15. Order Management and Execution

11 features: the core broker/execution integration, order-lifecycle reconciliation (DS-023), and the Advanced Market Tools set (Level II, DOM, time and sales, order ladder, hotkeys with mandatory hotkey-safety groundwork, bracket visualization). Bracket visualization is initial-release-required; most advanced tools are backlog. Owned by DS-002/DS-023.

## 16. Automation

3 features anchored on the already-approved five-automation-modes reconciliation (ADR-005). Owned by DS-011/DS-012.

## 17. Portfolios and Accounts

4 features: core portfolio tracking plus pointers to the fuller multi-account/multi-user/delegated-approval treatment in DS-020. Owned by DS-002/DS-020.

## 18. Journaling and Reviews

4 features, all already-approved requirements (DS-JRN-001 through DS-JRN-007) cross-referenced here for catalog completeness. DS-JRN-006 (Safe Progression) correctly remains `Future`, never `Planned`, per the Core Codex's already-verified classification. Owned by DS-002.

## 19. Options

2 features: selected options intelligence (product layer) and full options-chain analytics (long-term backlog). Both share the same blocker (options data provider not yet selected) with several downstream Screener/Calendar/Visualization/Exit features. Owned by DS-002.

## 20. Tax and Budget

2 features, both DS-013 backlog items (Tax Reporting, Budgeting) carried forward unchanged. Owned by DS-002.

## 21. Collaboration and Social

11 features spanning private collaboration/teams through the long-term public marketplace, with **two capabilities explicitly rejected at launch**: anonymous public copy trading and a public paid signal marketplace. Owned by DS-002 (new DS-ECO family, reassigned from DS-022 in the 2026-07-26 audit repair); DS-022 supports the creator-facing UX only.

## 22. Mobile

3 features: iOS/Android companion apps and mobile kill switches, all initial-release requirements. Owned by DS-016.

## 23. Web

2 features: the authenticated web account/dashboard (initial-release requirement) and the public marketing website (distinct surface, backlog). Owned by DS-016/DS-022.

## 24. Platforms and Distribution

4 features: Windows desktop packaging (initial-release requirement), release-channel model, and explicitly-deferred-but-groundwork-tracked macOS/Linux packaging. Owned by DS-016.

## 25. Subscriptions and Entitlements

5 features: billing, trials, grace mode, cancellation/export, and the entitlement quota engine. Owned by DS-019 (new DS-SUB/DS-ENT families).

## 26. Security and Privacy

5 features extending the existing, unaltered DS-008 security architecture: MFA, device trust, secret management for distributed clients, and Founder-asset extraction resistance (the single highest-value protection target in the system). Owned by DS-021 (new DS-DVT family).

## 27. Reliability and Recovery

5 features: the incident/recovery center, backup/DR operations, observability, SLOs, and cloud/model cost controls. Owned by DS-023 (new DS-REC/DS-DPR/DS-OBS/DS-CST families).

## 28. Design System and Accessibility

6 features extending DS-007's existing design/accessibility commitment, plus Morning Brief and Needs My Attention (both initial-release requirements). Owned by DS-022 (new DS-DSN family; DS-UX itself remains owned by DS-007, reused not duplicated).

## 29. Support and Administration

3 features: customer account administration, diagnostics/self-check tooling, and support intake. Owned by DS-019/DS-023.

## 30. Developer and Creator Ecosystem

3 features: creator strategy versioning, marketplace ownership/versioning groundwork, and the explicitly-excluded-from-initial-release white-label SDK. Owned by DS-002 (new DS-ECO family, reassigned from DS-022 in the 2026-07-26 audit repair); DS-022 supports the creator-facing UX only.

## 31. Commercial and Regional Availability

2 features: regional commercial restrictions and the explicitly-excluded-from-initial-release institutional routing. Owned by DS-019/DS-023.

## 32. Future Marketplace and Institutional Features

2 features at the Stage 9, year-5+ horizon: the public marketplace and global/institutional expansion. Owned by DS-022/DS-023.

## 33. Founder Developer Tooling

1 feature, added 2026-07-26: **Founder Sage Developer Mode** (`FEAT-0268`) -- a Founder-only, private, local-workstation AI coding/research assistant (repository inspection, code/test generation, failure diagnosis, diff preparation, Founder-review commit staging). Sandboxed and policy-bounded: no auto-push/merge/force-push/history-rewrite/protected-branch-deletion, no spending, no production-credential or secret access, no security/privacy-boundary changes, and no trading/broker authority merely because coding tools exist. Not required for the customer commercial release; groundwork begins Stage 1, usable private version targeted for Stage 3 Founder Workstation Beta. Represented as a `feature_id` (catalog-internal), not a new numbered DS requirement volume, so it does not change the Core Codex's controlled-ID totals. Owned by DS-018; supported by DS-015 (edition/repository boundary), DS-021 (sandboxing/secrets/repository security), DS-023 (logging/diagnostics/rollback/recovery/resource limits).

---

## Initial Release Boundary (Stage 5)

**Included:** Windows desktop; web account/dashboard; iPhone and Android companion apps; U.S. stocks and ETFs; selected options intelligence; professional core charting; common indicators; saved watchlists; smart watchlists; useful screeners; alerts; Morning Brief; Needs My Attention; Cloud Sage; Founder Local Sage remaining private; paper trading; tightly controlled live trading; stop loss; take profit; bracket orders; OCO orders where supported; trailing stops; break-even stops; partial exits; multi-target exits; risk-based position sizing; deterministic validation; journaling; portfolio exposure checks; mobile kill switches; subscriptions; grace mode; user data export; incident and recovery center; basic backtesting; limited market replay.

**Explicitly excluded:** full Pine Script competitor; public strategy marketplace; public social network; 100+ drawing tools; every global exchange; every exotic chart type; institutional routing; white-label SDK; advanced public copy trading; public paid signal marketplace.

Every feature above is queryable in `FEATURE_REGISTRY.csv` via `initial_release_required = Yes` and `release_stage = "Stage 5 -- Initial Commercial Release"`.

## Explicitly Rejected Capabilities

Two capabilities in this pass carry `implementation_status = Deprecated` and `groundwork_required_now = Explicitly Rejected` because they conflict with DarkSage's safety/verification principles at launch, not merely deferred priority:

- **Anonymous public copy trading** — unverified, anonymous replication of another user's trading activity.
- **Public paid signal marketplace** — paid distribution of unverified trading signals.

Both may be revisited only with a full verification/safety redesign in a future governance pass, per `FEATURE_GOVERNANCE.md`.

## Long-Term Ecosystem Backlog

Stage 8–9 features (private-collaboration maturity, creator ecosystem, public marketplace, global asset classes, institutional features) are tracked with `groundwork_required_now` values reflecting whether today's architecture must anticipate them (`Groundwork Required Now`, e.g. marketplace ownership/versioning model, private-team permissions) or can wait entirely (`Can Be Added Later...`, e.g. paper-trading competitions).

## Revision History

| Version | Date | Summary |
|---|---|---|
| 0.1.0 | 2026-07-25 | Initial foundation-pass master catalog covering 267 features across 32 categories. |
| 0.2.0 | 2026-07-26 | Independent-audit repair pass: corrected unsupported Implemented-status claims (FEAT-0003/0139/0140 -> Designed), resolved 11 initial-release/Idea features, added Founder Sage Developer Mode (FEAT-0268, category 33; 268 features total), corrected Founder-only platform assignments, and reassigned DS-DRW/DS-WCH/DS-VIZ/DS-CAL/DS-ECO primary ownership from DS-022 to DS-002 where content is normative business behavior rather than UX. |
