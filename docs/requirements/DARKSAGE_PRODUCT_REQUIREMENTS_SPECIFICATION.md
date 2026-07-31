# DSF-002 — DarkSage Product Requirements Specification

**Subtitle:** Product behavior, scope, safety, user experience, nonfunctional expectations, and acceptance contract

## 1. Document Control

| Field | Value |
|---|---|
| Document ID | DSF-002 |
| Title | DarkSage Product Requirements Specification |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |
| Source Baseline Commit | ec3a4ed (docs: complete DarkSage Codex consolidated cleanup) |
| Controlling Sources | DS-001 through DS-014 (as authored/approved); ADR-001–004; `ROADMAP.md`, `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `TRADING_RULES.md`, `SECURITY_RULES.md`, `AGENTS.md` |
| Publication Relationship | Governed for presentation purposes by [DSF-001 — DarkSage Publication Architecture](../publication/DARKSAGE_PUBLICATION_ARCHITECTURE.md), including its §A publication authority hierarchy; consolidates but does not replace, override, or reinterpret DS-001–DS-014. DSF-002 is a derived consolidation, not independent requirement authority — see §2. |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

### Document ID Rationale

Per `docs/standards/NAMING_AND_ID_STANDARD.md`'s `DSF-NNN` ("DarkSage Flagship Publication Document") namespace and [DSF-001](../publication/DARKSAGE_PUBLICATION_ARCHITECTURE.md) §Document ID Rationale, this document uses the authorized `DSF-NNN` prefix — it is not a Codex volume (`DS-NNN`), a requirement family (`DS-<DOMAIN>-NNN`), an ADR, a change proposal, or a design review. `DSF-002` is publication-only: it creates no requirement authority of its own, does not supersede Codex or root governance, and cannot establish product classification, implementation commitment, or architecture authority independently. Every normative statement in this document cites the `DS-<DOMAIN>-NNN` or `ADR-NNN` ID that actually holds authority for it.

## Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| 0.1.0 | 2026-07-25 | TheSinnerMan | First controlled draft. Consolidates DS-001 through DS-014's product-facing requirements into a single practical build contract, organized per §9's functional catalog. Authored alongside [DSF-001](../publication/DARKSAGE_PUBLICATION_ARCHITECTURE.md) in the same batch. Creates no new requirement authority; every statement cites its controlling `DS-<DOMAIN>-NNN` or `ADR-NNN` ID. |
| 0.2.0 | 2026-07-25 | TheSinnerMan | Targeted Critical/High repair (FLAG-H01–H04) following independent audit. **FLAG-H01:** Document Control and §2 "Relationship to the Codex" rewritten to state explicitly that DSF-002 is a derived consolidation, not independent requirement authority, and to reference DSF-001 §A's three-tier publication authority hierarchy; Document ID Rationale updated to cite `DSF-NNN`'s formal authorization in `docs/standards/NAMING_AND_ID_STANDARD.md`. **FLAG-H03:** every Journal classification occurrence (§8, §9.14, §10) corrected from an unsupported "Approved Future" (a DS-013 backlog status Journal was never assigned by any `DS-BL-NNN` entry) to a neutral, accurate formulation: non-committed roadmap direction without dedicated requirement or DS-013 backlog authority. **FLAG-H04:** §5's "future operator/support role" entry reworded to state absence rather than "open scope item"; §20's six-user private-deployment entry reworded as external deployment discussion rather than a pending decision; the corresponding invented item removed from §22's Open Questions list (renumbered 1–11), which now contains only questions already present in approved Codex sources. No DS-001–DS-014 volume, ADR, product requirement, safety/pipeline/roadmap/backlog/idea content, or Release Classification changed. |

## 2. Purpose

DSF-002 is a consolidated, practical restatement of DarkSage's product-facing requirements for use in day-to-day product, engineering, design, QA, and security work — a document a contributor can read start-to-end to understand what DarkSage is committed to build, what it is planned to build, and what remains exploratory, without needing to cross forty separate Codex files to assemble that picture.

**Intended audience:** product owners, engineering contributors across all specialist areas (backend, frontend, quant, trading, AI, QA, security), and independent auditors who need the practical shape of the product rather than the full governance apparatus behind it.

**Relationship to the Codex:** DSF-002 is a derived consolidation of DS-001 through DS-014, not an independent requirement authority. It does not replace, override, reinterpret, or reclassify any Codex requirement, and it does not itself originate product or engineering requirements — see [DSF-001](../publication/DARKSAGE_PUBLICATION_ARCHITECTURE.md) §A for the full three-tier publication authority hierarchy (controlling Codex/root Markdown → `DSF-NNN` Markdown → generated DOCX/PDF), to which this document is subordinate for all product and engineering meaning. Every requirement-level statement in this document cites its controlling Codex ID(s). Where a statement in this document is found to conflict with its cited controlling Codex requirement, the controlling Codex requirement governs, and the conflicting statement in this document is a defect to be corrected or regenerated — never a competing interpretation (per DS-ADR-010's conflict-resolution hierarchy, restated at §21 below).

**How to interpret requirements and summaries in this document:**
- A statement citing a `DS-<DOMAIN>-NNN` or `ADR-NNN` ID is a **direct requirement summary** — compressed, but not altered in meaning.
- A statement describing how requirements combine into a flow (§10 User Journeys) is a **derived summary** — useful for understanding, but the individual requirements cited within it remain the authoritative source of any single obligation.
- A statement explicitly marked **Illustrative Example** is an example, not a requirement — it never itself imposes an obligation.
- A statement explicitly marked **Non-Committed Reference** draws on DS-013 (backlog) or DS-014 (ideas) and creates no product commitment whatsoever (DS-BLG-001, DS-IDG-001).

## 3. Product Overview

DarkSage is a trading intelligence and decision-support platform (DS-001 §4). Its purpose is to help users investigate markets, test ideas, understand risk, and make better-informed decisions through evidence and explanation — not to predict markets, guarantee profit, or replace user judgment (DS-001 §21).

**Wisdom Over Noise** (DS-001 Foreword) is DarkSage's brand principle: markets produce more information than any person can continuously absorb, and DarkSage exists to turn that noise into structured understanding while preserving the user's authority.

**Technology should help users think more clearly, not think for them** (DS-001 Foreword, Appendix A #1). DarkSage's core values — Clarity, Evidence, User Authority, Visible Risk, Explainability, Privacy and Security, Restraint (DS-001 §8) — all flow from this.

**Sage advises; the user decides** (DS-001 §12, restated as DS-003's Core Rule and enforced as ADR-002/DS-PRD-006, Committed/MVP). Sage — DarkSage's AI-assistance layer — may reason, synthesize, explain, and personalize, but never becomes an unquestionable authority and never gains execution authority over trading decisions, regardless of confidence, urgency, user authorization, or which AI provider generated a proposal.

**No Trade as a valid outcome** (`TRADING_RULES.md` "AI Abstention"; DS-001 §9). AI is permitted — and expected — to return "no trade," "insufficient confidence," "conflicting evidence," or "more data required." Not trading is a valid decision, not a failure mode.

**Local-first and cheap-first where practical** (DS-001 §14; `PROJECT_SPEC.md` §2.1 Cheap-First Architecture; `AGENTS.md` "Cheap-First Development"). DarkSage prefers deterministic local code, then local AI, then free API tiers, then paid services only when justified — a preference, not an absolute promise that no data ever leaves a device.

**Deterministic calculations remain deterministic** (DS-001 Constitution #6; ADR-003; DS-PRD-004, Committed/MVP). Material financial calculations — risk metrics, backtest statistics, position/portfolio math, indicator values — come from deterministic, testable implementations, never from generative model output.

## 4. Goals and Success Measures

DarkSage's product goals, per DS-001 §6–§7 (Vision/Mission) and the requirement families that operationalize them:

| Goal | Grounding | Committed Now? |
|---|---|---|
| Transparent opportunity ranking | DS-SCN-003 (Ranking and Scoring); DS-SIG-002 (Signal Grading) | Committed/MVP |
| Reproducible analysis | DS-PRD-004 (Deterministic Financial Truth); DS-QA-004/005 | Committed/MVP |
| Explainable evidence and contradictions | DS-PRD-002 (Evidence Provenance); DS-SIG-003 (Why-Trade/Why-Not-Trade); DS-SGE-009 (Planned) | Committed/MVP (Signal surface); Planned (Sage conversational surface) |
| Realistic paper simulation | DS-BKT-002 (Realistic Transaction Costs and Slippage); DS-EXE (Paper Auto-Trader family) | Planned |
| Deterministic safety | DS-RSK-001/002 (Committed); ADR-002/003 | Committed/MVP |
| Accurate provenance and freshness | DS-PRD-008 (Data State Visibility); DS-MKT-003/004 | Committed/MVP |
| Extensible providers | DS-ARC-006 (Market Data Provider Abstraction); DS-EXE-006 (Broker Adapter, Planned); DS-ARC-013 (AI Provider Interface, Planned) | Committed/MVP (market data); Planned (broker, AI) |
| Desktop-to-mobile evolution | ADR-001 (Desktop-First, preserves future extensibility); DS-ARC-003/DS-MOB (Planned, Phase 9) | Planned |
| Future controlled live operation without architectural rewrite | DS-RM-006 (Gate-chain, DS-011); DS-EXE-007 (Live Trading Gate, Committed governance boundary) | Committed governance boundary; Planned implementation |

DarkSage's stated Non-Goals (DS-001 §21, restated by DS-002 §9) bound these goals: it is not a promise of profit, not a guaranteed market predictor, not a substitute for user judgment, not an opaque autonomous trader, and not a platform where AI output is unquestionable truth or where UI layout silently changes analytical capability.

## 5. Users and Roles

Per DS-002 §8 (capability-based, not demographic, groups) and DS-USR-004 (Persona presets, Planned):

- **Developing / self-directed investor** — learning markets, values explanation and guardrails over raw power.
- **Active trader** — values speed of access to relevant information, scanning, and alerting.
- **Advanced / professional-style user** — values analytical depth, customization, and minimal friction from simplified defaults.
- **Administrator** — a permission group named in `SECURITY_RULES.md` "Authentication and Authorization" (administrative settings) and DS-API-COR-004's minimum permission-group list; DarkSage's Committed/MVP scope defines this permission group's existence but not a distinct multi-tenant administrator product experience.
- **Reviewer/auditor** — the role this document itself, `docs/traceability/TRACEABILITY_MATRIX.csv`, and `AGENTS.md`'s independent-review requirements are written for; not a distinct in-product persona, but a governance/process role with read access to audit logs (DS-API-OPS-001, Committed) and traceability records.
- **Future operator/support role** — no controlling source currently defines this role. It is absent from DarkSage's current scope: DS-API-COR-004's minimum permission-group list (read-only, trade approval, Auto-Trader control, administrative settings, live-trading management) is the full extent of role/permission definition in the approved Codex. This is not a pending question for §22 — a role with no controlling-source definition is simply out of scope, not an open decision.

**Permissions and trust distinctions:** DS-API-COR-004 (Committed/MVP) fixes the minimum permission-group vocabulary; DS-USR-006 (Local User Profile Identity, Planned) establishes that core local functionality requires no mandatory external account, and that a single local profile is the Committed/MVP baseline — multi-profile support beyond one default profile is Planned, not yet committed.

A persona/permission-group distinction is deliberate: personas (DS-USR-004) affect only default presentation (never capability, per Presentation Independence, ADR-004); permission groups (DS-API-COR-004/DS-SCA-005) affect actual authorization. The two vocabularies are never substituted for each other.

## 6. Platforms and Deployment

- **Desktop-first** (ADR-001, Committed/MVP direction): Electron + React + TypeScript, location `apps/desktop/` (DS-ARC-002, Committed/MVP for the Phase-1 baseline shell: navigation, dashboard, scanner page, signal list, signal detail). The desktop client never contains critical trading logic (DS-ARC-001, Committed/MVP) — it is always a client of the backend API.
- **Mobile companion** (DS-ARC-003/DS-MOB-001, **Planned, Phase 9**): React Native, iPhone-first, Android-ready-later. Even before Phase 9 implementation begins, DS-MOB-002 (Committed/MVP governance boundary) fixes now that mobile shall never independently run the scanner, backtester, or execution engine, and shall never store authoritative trading state — it always observes and can only trigger changes to backend-authoritative state (DS-ARC-001).
- **Backend-authoritative state** (DS-ARC-001, Committed/MVP): the backend (`backend/`, Python/FastAPI) is the sole source of truth for trading and account state (positions, orders, portfolios, signals, strategies, risk state, broker state) regardless of how many client surfaces exist.
- **Local development** (DS-ARC-018 Stage 1, Committed/MVP): local-only, target hosting cost $0/month; SQLite as the initial database (DS-ARC-016, Committed/MVP) with PostgreSQL/TimescaleDB migration deferred to Phase 12, not committed to current scope.
- **Future hosted backend** (DS-ARC-018 Stage 3, not committed to current scope): critical backend services move to an always-on server only once Phase 12 (Production Hardening) is reached.
- **Local and optional cloud AI** (DS-ARC-014, Planned, Phase 6): local AI is the default and preferred provider; cloud AI (OpenAI, Anthropic, Google Gemini, custom OpenAI-compatible endpoints) is optional, user-configured with the user's own API key, and never required for basic application operation or for any deterministic calculation.
- **Degraded/offline behavior** (DS-OPS-004, Committed/MVP): DarkSage remains usable for local-only capability (workspace use, locally stored data, deterministic calculations on local data) when network/external services are unavailable, with degraded capability explicitly disclosed rather than silently failing.

## 7. Product Modes

Per `TRADING_RULES.md` "Trading Modes" and `PROJECT_SPEC.md` §3, DarkSage supports five trading modes, each with distinct strategy preferences, timeframes, risk rules, holding periods, and performance statistics:

| Mode | Focus | Typical Holding Period |
|---|---|---|
| Scalping / Day Trading | Intraday timeframes, momentum, opening-range breakouts, VWAP, relative volume, intraday support/resistance, news catalysts, tight risk controls | Intraday (optional close-all-before-close rule) |
| Swing | 1H/4H/Daily, breakouts, momentum, pullbacks, trend following, reversals, sector strength | Several days to several weeks |
| Position | Daily/Weekly, technical and fundamental combination | Multi-week to multi-month |
| Long-Term | Fundamentals (revenue/earnings growth, FCF, debt, margins, ROE/ROIC, valuation, competitive strength, dividend quality) | Months to years |
| Custom | User-defined | User-defined |

**Capital buckets:** Portfolio profiles (DS-PRT family, Planned) include Aggressive Growth, Balanced Growth, Conservative, Income, and Custom (`PROJECT_SPEC.md` §4).

**Risk and timeframe differences across modes** are governed by the same Risk Engine (DS-RSK-001/002, Committed/MVP) and Strategy Performance segmentation (DS-PERF-002, Planned, which explicitly segments by timeframe and market regime among other dimensions) — DarkSage does not implement a separate risk engine per mode.

## 8. Major Product Workspaces

Per `ARCHITECTURE.md` §3 (Phase-1 baseline) and DS-WKS (Workspace Studio):

| Workspace | Committed Now? | Governing Requirements |
|---|---|---|
| Home / Market Dashboard | Committed/MVP (Phase-1 shell) | DS-ARC-002, DS-WKS-001 |
| Scanner | Committed/MVP | DS-SCN-001/002/003 |
| Signals | Committed/MVP | DS-SIG-001/002/003 |
| Chart Workspace | Committed/MVP | DS-CHT-001/002 |
| Portfolio | Planned | DS-PRT-001–004 |
| Strategy Lab | Planned | DS-STR-001–003, DS-BKT-001–004 |
| Knowledge / Learn | Planned (contextual reference) / Future-Exploratory (full Knowledge Engine) | DS-EDU-001 (Planned), DS-EDU-002 (Future/Exploratory), DS-ARC-025 (Planned) |
| Auto-Trader | Planned, Phase 7 | DS-EXE family |
| Journal | Non-committed roadmap direction without dedicated requirement or DS-013 backlog authority — named in `ROADMAP.md` Phase 7 deliverables ("Trade journal") as directional sequencing only; **no dedicated DS-002 requirement family exists yet.** Not to be presented as a currently-specified feature. | `ROADMAP.md` Phase 7 (directional only) |
| Sage | Planned, Phase 6 | DS-AI-001–007, DS-SGE family |
| Settings | Committed/MVP (credential/integration management baseline) | DS-INT-002, DS-API-INT-001 |
| Mobile companion | Planned, Phase 9 | DS-MOB-001–003, DS-ARC-003/024 |

All workspaces are subject to Presentation Independence (ADR-004, DS-PRD-003, Committed/MVP): removing or hiding a workspace's widgets never disables the underlying capability, and Sage's evidence access never depends on which workspace widgets happen to be visible.

## 9. Functional Requirement Catalog

Each entry below states: controlling ID(s), title, classification, priority (where controlled), a concise behavior statement, user value, key dependencies, an acceptance summary, notable edge cases, verification direction, and explicit scope status. Full acceptance-criteria text remains authoritative in its source `DS-<DOMAIN>-NNN` family document; this catalog consolidates rather than duplicates it.

### 9.1 Users, Authentication, Sessions, and Workspace State

| ID | Title | Class. | Pri. | Behavior / User Value / Verification |
|---|---|---|---|---|
| DS-USR-001 | First-Run Onboarding | Planned | High | Routes a new (no-prior-profile) user to a bounded, skippable onboarding flow rather than an empty workspace. Skipping leaves a usable state with documented defaults. Verification: no-prior-profile routing test; skip-to-default test. |
| DS-USR-002 | User Preferences Persistence | Planned | High | Persists terminology mode, workspace defaults, notification settings locally; corrupted storage falls back to safe defaults, never a crash. Verification: restart-persistence test; corrupted-storage fallback test. |
| DS-USR-003 | Professional / Codex-Themed Terminology Modes | Planned | Medium | User-selectable label vocabulary (DS-001 §17) that changes display labels only, never capability, data, or calculation results (DS-PRD-003). Verification: mode-switch functional-equivalence regression test. |
| DS-USR-004 | Capability-Based User Personas | Planned | Medium | Persona presets (developing/active-trader/advanced) adjust only default presentation density/terminology suggestion — never gate capability (DS-001 §18). Verification: cross-persona capability-parity test. |
| DS-USR-005 | Progressive Disclosure of Advanced Capability | Planned | Medium | Default views stay approachable while every Committed/MVP capability remains reachable by advanced users without a workspace rebuild. |
| DS-USR-006 | Local User Profile Identity | Planned (single-profile baseline; multi-profile Planned separately) | Medium | Core local functionality requires no mandatory external account; any optional external/cloud account is explicitly opt-in. |
| DS-WKS-001 | Configurable Workspaces | **Committed/MVP** (Phase-1 shell baseline) | High | Add/remove/resize/arrange Committed/MVP widgets without affecting other workspaces or underlying capability. Verification: add/remove/resize round-trip regression per widget. |
| DS-WKS-002 | Drag-and-Drop Layout | Planned | Medium | Direct drag-and-drop repositioning with a documented deterministic collision rule and cancellable in-progress drag. |
| DS-WKS-003 | Saved Workspace Layouts | Planned | High | Save/name/load/delete multiple layouts; at least one default layout exists for a fresh profile. |
| DS-WKS-004 | Purpose-Specific Workspaces | Planned | Medium | Switching active workspace never alters/discards other saved layouts. |
| DS-WKS-005 | Information Density Control | Planned | Low | Compact/comfortable density is presentation-only, never functional. |
| DS-WKS-006 | Multi-Monitor Support | **Future/Exploratory** | Low | Not committed to current scope; owner decision pending (DS-002 Appendix A #3). |
| DS-API-COR-004 | Authentication and Authorization | **Committed/MVP** | — | Every non-public endpoint requires backend-enforced authentication; authorization evaluated separately against permission groups (read-only, trade approval, Auto-Trader control, administrative settings, live-trading management). Authenticated-but-unauthorized → 403, distinct from unauthenticated → 401. |
| DS-API-COR-010 | Session Lifecycle Contract | **Committed/MVP** | — | Login/logout/refresh/list-sessions/revoke-one/revoke-all, mechanism-agnostic (credential format is Open Question #2, DS-006 Appendix A). Revocation takes effect without backend restart; the raw session credential is never exposed by `GET /auth/sessions/current`. |
| DS-API-WKS-001 | Active Workspace Composition | **Committed/MVP** (ephemeral, session-scoped) | — | Read/write in-session workspace composition; does **not** imply durable cross-session persistence — that is DS-API-WKS-002 (Planned). |
| DS-API-WKS-002 | Persisted and Saved Workspace Layouts | Planned | — | Durable, named, multi-layout CRUD, superseding WKS-001's ephemeral store once implemented. |

### 9.2 Market Data and Provenance

| ID | Title | Class. | Pri. | Behavior / Verification |
|---|---|---|---|---|
| DS-MKT-001 | Market Data Ingestion | **Committed/MVP** | Critical | Normalizes ingested price/volume data to one internal schema regardless of vendor; every record carries source and ingestion timestamp; malformed records rejected individually. |
| DS-MKT-002 | Historical Market Data | **Committed/MVP** | High | Historical data retrievable for symbols the user has interacted with; immutable once stored except via explicit logged correction; coverage gaps discoverable, never silently interpolated. |
| DS-MKT-003 | Real-Time and Delayed Data Handling | **Committed/MVP** | High | Every quote/price surface indicates real-time vs. delayed, and delay duration when delayed; no Committed/MVP surface shows delayed data unlabeled. |
| DS-MKT-004 | Data Freshness Thresholds | **Committed/MVP** | High | Controlled default thresholds: real-time stale at **10s** no-update; delayed stale at delay-window **+ 60s**; EOD/historical stale at **1hr post-close**. Staleness evaluation accounts for market-session state so closed-market values aren't falsely flagged. |
| DS-MKT-005 | Market Calendars and Trading Sessions | **Committed/MVP** | Medium | Session-state (pre-market/regular/post-market/closed/holiday) queryable per market/date; **the specific set of supported markets is an Owner Decision, not fixed by this requirement.** |
| DS-MKT-006 | Corporate Actions Handling | Planned | Medium | Splits/dividends/symbol changes preserve historical continuity and position accuracy (DS-PRD-004); unrecognized events flagged for review, never silently applied. |
| DS-MKT-007 | Watchlists | Planned | High | Multiple, independently editable, persistent watchlists; invalid/delisted entries flagged, not silently removed. |
| DS-PRD-008 | Data State Visibility | **Committed/MVP** | High | Users and Sage can distinguish stale/delayed/historical/simulated/current data wherever material; mixed-state views label each item individually. |
| DS-API-MKT-001–003 | Quote/Candle Retrieval, Symbol Lookup, Market Calendar | **Committed/MVP** | — | Out-of-range requests return the available subset with an explicit truncation indicator rather than fabricating data; delisted-and-reused ticker search disambiguates rather than merging identities. |

### 9.3 Scanner and Watchlists

| ID | Title | Class. | Pri. | Behavior / Verification |
|---|---|---|---|---|
| DS-SCN-001 | Deterministic Pre-Filtering | **Committed/MVP** | High | Deterministic filter criteria evaluated and applied **before** any AI-model call for that scan (DS-001 §9 Restraint); a scan with zero AI steps functions correctly on deterministic filtering alone. |
| DS-SCN-002 | Scan Configuration and Execution | **Committed/MVP** | High | Saved scan configs re-execute against current data on demand; execution reports which symbols were evaluated/passed and why. |
| DS-SCN-003 | Ranking and Scoring | **Committed/MVP** | Medium | Rank/score explainable on request; AI-assisted scoring components labeled and never presented with deterministic-component certainty (DS-PRD-009); ties resolved by a documented deterministic rule. |
| DS-SCN-004 | AI-Assisted Scan Analysis | Planned | Medium | Operates only on the already-filtered set; scan can be configured to skip the AI step and still produce a complete deterministic result. |
| DS-SCN-005 | Scan Result History | Planned | Low | Prior executions retrievable with timestamp; viewing history never re-executes against current data. |

### 9.4 Signals and Lifecycle

| ID | Title | Class. | Pri. | Behavior / Verification |
|---|---|---|---|---|
| DS-SIG-001 | Signal Representation | **Committed/MVP** | High | Structured Signal record: symbol, direction, confidence, quantitative/technical/fundamental/sentiment scores, patterns, indicator snapshot, reasoning, timestamp, expiration. Reasoning text derives from deterministic scoring inputs, not free generation. |
| DS-SIG-002 | Signal Grading | **Committed/MVP** | Medium | A+/A/B/C/D grade derived deterministically from measurable inputs — **never assigned by unstructured AI judgment alone.** Insufficient inputs grade conservatively low, never mid-range default. |
| DS-SIG-003 | Why-Trade / Why-Not-Trade Explanation | **Committed/MVP** | High | Every accepted or rejected signal carries a machine-readable reason set from a fixed vocabulary (poor risk/reward, weak expectancy, insufficient sample size, earnings risk, low liquidity, wide spread, market regime mismatch, sector concentration, correlated exposure, risk budget exhausted, stale data, bad data, strategy suspended). Multiple simultaneous reasons all recorded, never collapsed to one. |
| DS-SIG-004 | Signal Expiration | Planned | Low | An expired signal is visually/textually distinguished from an active one. |

### 9.5 Charts and Visualization / Indicators

| ID | Title | Class. | Pri. | Behavior / Verification |
|---|---|---|---|---|
| DS-CHT-001 | Price Charting | **Committed/MVP** | High | Candlestick/OHLC + volume rendering via dual engines (Apache ECharts, TradingView Lightweight Charts); indicates data state per DS-PRD-008. |
| DS-CHT-002 / DS-ARC-007 | Technical Indicators and Overlays / Single Shared Indicator Engine | **Committed/MVP** | Medium | Each indicator implemented exactly once and used identically by chart, scanner, backtester, and (later) Auto-Trader — no duplicate math. Phase-1 set: SMA, EMA, RSI, MACD, ATR, Bollinger Bands, VWAP, ADX, OBV, Relative Volume, Relative Strength — each unit-tested against known reference data. |
| DS-CHT-003 | Chart Annotations | Planned | Low | User annotations persist per symbol/chart; never affect calculation, indicator, or Sage evidence (DS-PRD-003). |
| DS-CHT-004 | Sage-Chart Evidence Linkage | Planned | Medium | Sage can cite chart-derived evidence even when no chart widget is present (Presentation Independence). |
| DS-ARC-008 | Chart Adapter Abstraction | **Committed/MVP** | High | Both engines render identical market data/indicator values/trade markers for identical input — rendering is a choice, never a second computation source. |

### 9.6 Pattern Recognition and Knowledge Engine

| ID | Title | Class. | Pri. | Behavior / Verification |
|---|---|---|---|---|
| DS-ARC-025 | Trading Knowledge Engine Architecture | Planned, Phase 5 | Low | Deterministic local code (`backend/app/knowledge/` — single authoritative path) that structures, scores, retrieves, explains, and statistically validates trading concepts; reuses existing `patterns/`/`indicators/` modules rather than duplicating math. Detection, setup-quality scoring, and trade eligibility remain three distinct, non-conflatable steps — a high setup-quality score never grants, skips, or shortcuts any `TradeValidationPipeline` stage. |
| DS-EDU-001 | Contextual Terminology Reference | Planned | Low | On-demand definitions/explanations reachable without leaving current context; an undefined term discloses the gap rather than fabricating an explanation. |
| DS-EDU-002 | Trading Knowledge Engine (full capability) | **Future/Exploratory** | Low | Non-binding future direction (DS-001 §19.2); not committed to current MVP or Planned scope. |

**Non-Committed Reference:** `ROADMAP.md` Phase 5's full chart/candlestick pattern catalog (triangles, wedges, flags, head-and-shoulders, etc.) and contextual setup-quality scoring model are named directionally in `ARCHITECTURE.md` §31/`PROJECT_SPEC.md` §33 and are Planned-Phase-5 implementation detail governed by DS-ARC-025 above — no separate DS-002 requirement enumerates each individual pattern.

### 9.7 Scoring, Confidence, Eligibility, and Ranking

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-PRD-009 | Uncertainty Communication | **Committed/MVP** | High | Probabilistic/model-generated forecasts never represented as deterministic future facts; consistent, defined confidence vocabulary reused across all surfaces. |
| DS-SGE-014 | Confidence Vocabulary Definition | Planned, Phase 6 | High | A fixed, small confidence-label set (e.g., high/moderate/low/insufficient evidence), used verbatim across Sage output; borderline cases default to the lower-confidence label. |

**Eligibility boundary (Committed, unconditional):** a detected pattern, a scored setup, or a signal grade is never itself a trade — trade eligibility is decided exclusively by the canonical `TradeValidationPipeline` (§11), per `TRADING_RULES.md` "Pattern Detection Is Not a Trade Signal" and DS-EXE-001 (Committed/MVP).

### 9.8 Holding-Time and Thesis-Clock Behavior

**Non-Committed Reference:** Thesis tracking and "thesis-broken" alerts are named directionally in `PROJECT_SPEC.md` §22 (Portfolio Research Features) and referenced by DS-PRT-004's Portfolio Overview requirement (Planned) as a category of material risk indicator it may aggregate — but **no dedicated DS-002 requirement currently defines thesis-clock mechanics, a holding-time model, or thesis-invalidation logic.** This is recorded here as an open scope item, not invented as a requirement.

### 9.9 Research and Catalysts / SEC, Insiders, Congress, Institutions, Macro, Alternative Data

**Non-Committed Reference (all items below).** None of the following carries a Release Classification; they are DS-013 backlog candidates or DS-014 research ideas, included here only so this catalog is complete about what is *not* yet committed:

- Political/legislative-trading intelligence (SEC/Congress disclosures) — DS-BL-010, Status **Candidate**, no current Codex grounding; requires legal review before any promotion.
- Insider/institutional context — named directionally in `ROADMAP.md` Phase 10 ("Insider/institutional context where data permits"); no dedicated DS-002 requirement yet.
- Macro/economic regime engine, sector rotation, market breadth — `ROADMAP.md` Phase 10, Future/Exploratory per DS-RM-012 (roadmap-phase inclusion alone never promotes an item).
- Cross-asset/alternative data (options/order-flow intelligence) — DS-IDEA-012 (DS-014, Exploratory), distinct from DS-BL-007 (options *trading*, Deferred).
- SEC filing/news/fundamental fusion — DS-IDEA-013 (DS-014, Exploratory).

### 9.10 Strategy Builder and Playbooks

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-STR-001 | Strategy Construction | Planned | High | Structured, deterministically-evaluable entry/exit rules, applicable instruments, and parameters, saved for reuse; construction alone never places, schedules, or queues a live order (DS-PRD-007). |
| DS-STR-002 | Strategy Validation | Planned | High | Structural validation (referenced fields exist, parameters in range, no contradictions) blocks execution with a specific actionable error. |
| DS-STR-003 | AI-Assisted Strategy Authoring | Planned | Medium | Sage may help draft a strategy's structured rules from natural language, subject to the same validation and explicit user confirmation before saving — no bypass of DS-STR-002. |

### 9.11 Backtesting and Anti-Overfitting

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-BKT-001 | Deterministic Historical Backtesting | Planned | Critical | Identical strategy/data/config → identical results across runs (ADR-003); output states exact data range, strategy version, and configuration used. |
| DS-BKT-002 | Realistic Transaction Costs and Slippage | Planned | High | Default configuration includes **non-zero** cost/slippage assumptions, always disclosed alongside results; a user-set zero-cost run is explicitly labeled idealized/frictionless. |
| DS-BKT-003 | Look-Ahead Bias and Data Leakage Prevention | Planned | Critical | A decision at simulated time T cannot access data with a knowledge timestamp later than T; hard-enforced boundary, including for corporate-action revisions. |
| DS-BKT-004 | Backtest Result Disclosure | Planned | High | Every backtest result carries the disclosure that historical/simulated performance is not a guarantee of future performance (DS-001 §13); output visually distinguishable from live performance. |
| DS-PERF-004 | Anti-Overfitting Safeguards | Planned | High | Minimum sample-size requirements, multiple-testing protection, false-discovery warnings, parameter-stability analysis, out-of-sample and walk-forward validation before promotion; **no strategy may be promoted solely because of an impressive in-sample backtest.** |

### 9.12 Strategy Intelligence

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-PERF-001 | Performance Metric Tracking | Planned | Medium | Trade count, wins/losses, win rate, expectancy, profit factor, average win/loss, max drawdown, Sharpe, Sortino, sample-size confidence, tracked per strategy. Acceptance criteria deferred to Phase 3 authoring. |
| DS-PERF-002 | Performance Segmentation | Planned | Medium | Segmented by strategy/version, symbol, sector, timeframe, market regime, instrument, entry/exit method, time of day, day of week — a low-sample segment disclosed as low-confidence, never weighted equally with a well-sampled one. |
| DS-PERF-003 | Strategy DNA | Planned | Low | Per-stock profile (best/worst strategies, best timeframe/regime, volatility, mean-reversion tendency) based on **measured statistical evidence, never AI guessing** — this specific constraint is fixed now even though the rest is deferred to Phase 3. |
| DS-ARC-020 | Strategy Performance and DNA Architecture | Planned | Medium | Reuses backtesting's statistical infrastructure; "a model's guess is never a substitute for computed statistics" fixed now. |

### 9.13 Portfolio Intelligence

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-PRT-001 | Position Tracking | Planned | Critical | Position quantity/cost basis computed deterministically from transaction history; corporate actions update positions consistently (DS-MKT-006). |
| DS-PRT-002 | Transaction Recording | Planned | Critical | Transactions (DS-DB-025, append-only ledger) are immutable once confirmed; corrections use explicit logged reversing/adjusting entries, never silent edits. |
| DS-PRT-003 | Realized and Unrealized Performance | Planned | High | Deterministic P/L using current/last-known market data with disclosed data state; reproducible from stored transactions and the market-data snapshot used. |
| DS-PRT-004 | Portfolio Overview | Planned | Medium | Every figure traces to its authoritative calculation (position/performance/risk engine) — never a separately computed duplicate. |

### 9.14 Journal and Behavioral Review

**Non-committed roadmap direction without dedicated requirement or DS-013 backlog authority.** "Trade journal" appears in `ROADMAP.md` Phase 7's deliverable list; `ROADMAP.md` provides directional sequencing only, and no dedicated DS-002 requirement or `DS-BL-NNN` backlog entry currently grants Journal a controlled implementation status. Per DS-RM-012 (roadmap phase-list inclusion never itself promotes an item to Committed or Planned), Journal is preserved here as a conceptual/directional product area — neither approved nor rejected — pending its own dedicated requirement authoring. This document does not invent journal/behavioral-review acceptance criteria that do not yet exist in the Codex.

### 9.15 Sage and AI Providers

See §13 for the full consolidated Sage requirement summary. Key IDs: DS-AI-001–007 (Planned, Phase 6), DS-SGE-001–020 (DS-003, Planned, Phase 6, except DS-SGE-012 Persistent Memory which is Future/Exploratory), DS-ARC-013 (AI Provider Interface, Planned), DS-ARC-014 (Local-First AI, Planned), DS-ARC-015 (AI Provider Credential Handling, **Committed/MVP**).

**Unconditionally Committed regardless of Sage's own Planned classification:** DS-PRD-001 (Model Independence), DS-PRD-002 (Evidence Provenance), DS-PRD-003 (Presentation Independence), DS-PRD-004 (Deterministic Financial Truth), DS-PRD-005 (User Decision Authority), DS-PRD-006 (Risk Engine Authority), DS-PRD-007 (No Unapproved Autonomous Trading), DS-PRD-008 (Data State Visibility), DS-PRD-009 (Uncertainty Communication), DS-PRD-011 (AI Output Validation).

### 9.16 Alerts and Notifications

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-ALT-001 | User-Configured Alerts | Planned | High | Alert firing **never** places, schedules, or queues a trade — notification only (DS-PRD-007); fired alerts recorded and reviewable; duplicate rapid-fire triggering deduplicated per a documented cooldown rule. |
| DS-ALT-002 | Notification Delivery | Planned | Medium | Fired alert visible regardless of currently displayed workspace (DS-PRD-003); notification history retrievable after the app was closed/backgrounded. |
| DS-ALT-003 | External Notification Channels | Planned | Low | Opt-in, disabled by default; failure of an external channel never suppresses the in-app notification. |
| DS-API-ALT-001 | Alert Configuration | Planned | — | No operation on this endpoint group can create an Order or reach the Execution/Broker domain — no request-body field on any operation can specify broker/order data. |

### 9.17 Paper Auto-Trader

See §11 for the full canonical trade/safety model. Key IDs: DS-EXE-001 (**Committed/MVP** — pipeline is the only path to an order), DS-EXE-002/003/006 (Planned, Phase 7), DS-EXE-004/005 (Emergency Stop/Flatten, Planned Phase 7 implementation with fixed acceptance criteria now), DS-EXE-007 (**Committed/MVP** governance boundary — live-trading gate).

### 9.18 Risk, Permissions, Exposure, Buying Power, Market Condition, Order Validation, Broker Boundaries

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-RSK-001 | Risk Engine Independent Authority | **Committed/MVP** | Critical | No external caller — **including a future Sage** — can modify, bypass, disable, silently override, or substitute for the Risk Engine. Fail-safe (block/warn) on unavailability, never an implicit allow. Risk configuration changes require explicit user/administrative action only. |
| DS-RSK-002 | Deterministic Position and Risk Calculations | **Committed/MVP** | Critical | Identical inputs → identical output; missing required data discloses a calculation gap, never defaults to a misleading zero/neutral value. |
| DS-RSK-003 | Risk Limits and Warnings | Planned | High | Configured limit breach surfaces at the point of relevant decision, not buried in a separate report; never suppressed by workspace layout. |
| DS-RSK-004 | Scenario Analysis | Planned | Medium | Deterministic, reproducible scenario output; discloses assumptions, never presented as a prediction. |
| DS-RSK-005 | Risk Disclosure in Sage Output | Planned | High | Sage discloses material downside/risk when referencing an opportunity — never omitted to appear more attractive. |
| DS-ARC-012 | Risk/Permissions as Distinct Pipeline Stages | Planned, Phase 7 (unconditional boundary Committed via DS-EXE-001) | Critical | Risk Engine and Permissions Engine exist as distinct, independently testable pipeline stages; neither may be bypassed, merged, or reordered. |
| DS-API-RSK-001 | Risk Engine Query (Read-Only) | **Committed/MVP** (query boundary) | — | No request body on this endpoint group can alter a risk rule or determination; rule changes exposed only via a distinct admin-gated surface. |

### 9.19 Mobile Companion

See §6 (Platforms) and §14 for consolidated mobile requirements. Key IDs: DS-MOB-001 (scope, Planned, Phase 9), DS-MOB-002 (**Committed/MVP governance boundary** — mobile cannot run core trading logic), DS-MOB-003 (strong authentication for high-risk mobile actions, Planned, Phase 9), DS-ARC-003/024 (Planned).

### 9.20 Settings and Credentials

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-INT-001 | External Data Provider Boundary | Planned | High | No Committed/MVP DS-MKT requirement's acceptance criteria names a specific vendor as mandatory. |
| DS-INT-002 | Credential-Based Integration Configuration | **Committed/MVP** | High | No external integration activates without explicit user configuration; Settings surface lists active integrations and allows removal/deactivation; invalid credentials shown as degraded/inactive, never silently failing. |
| DS-INT-003 | Manual Brokerage/Execution Connectivity | Planned | Medium | Read-only brokerage import functions independent of order-placement capability; any future order-placement integration requires per-order explicit user confirmation and remains subject to DS-PRD-007 regardless of timing. Governing owner decision recorded as DS-002 Appendix A Open Question #2. |
| DS-SEC-001 | Credential and Secrets Handling | **Committed/MVP** | Critical | No log/export/error message from a Committed/MVP feature contains a raw credential value; OS-appropriate secure storage, never plaintext configuration files. |
| DS-ARC-015 | AI Provider Credential Handling | **Committed/MVP** | Critical | API keys never committed/logged/exposed in frontend source; a stored key never redisplayed in full once saved; a key never sent to a provider other than the one configured for it. |
| DS-API-INT-001 | Integration Credential Management | **Committed/MVP** | — | Every read returns metadata only, never a usable secret; delete errors 409 if credential is in use. |

### 9.21 Auditability and Data Quality

| ID | Title | Class. | Pri. | Behavior |
|---|---|---|---|---|
| DS-OPS-001 | Application Logging | **Committed/MVP** | High | Material events (startup, ingestion failures, Risk Engine determinations, crashes) logged locally, excluding secrets. |
| DS-OPS-002 | Auditability of Risk and Sage Determinations | **Committed/MVP** | High | Risk Engine determinations and related Sage output logged with correlated timestamps for after-the-fact reconstruction. |
| DS-SCA-020 | Security Event Audit Logging | **Committed/MVP** | — | Login, failed login, credential change, live-trading enable, Auto-Trader enable/disable, risk-limit changes, Emergency Stop/Flatten, trade override, and permission changes are each audited. |
| DS-SCA-025 | Audit-Log Integrity and Protection Architecture | **Committed/MVP** | — | Audit records append-only; a correction is a new linked entry, never an edit; if audit persistence itself is unavailable, the triggering security-sensitive action fails closed rather than proceeding unaudited. |
| DS-SCA-027 | Audit-Log Integrity Verification Contract | **Committed/MVP** | — | Deterministic detection of modification/reordering/truncation/deletion/insertion at four fixed triggers (startup, before security-sensitive review, scheduled, post-fault); a compromised range is never silently rebuilt to pass verification — violations escalate through DS-SCA-026's incident lifecycle. |
| DS-QA-012 | Data Quality and Freshness Testing | **Committed/MVP** | — | Feed-interruption simulation confirms stale/delayed indicators appear within DS-MKT-004's threshold windows. |

### 9.22 Responsive Loading, Caching, Tooltips, and Safe Optimistic Rendering

**Approved Future — DS-013 backlog item, not yet a DS-007 requirement.** DS-BL-027 ("Responsive Loading and Interaction Feedback," DS-013, Status Approved Future, Founder-approved) records this direction and its **Hard Safety Boundary**: optimistic rendering is prohibited for trades/orders, broker actions, risk-limit changes, permission changes, Emergency Stop/Flatten, credentials, authentication state, strategy promotion/activation, and any other irreversible or safety-critical action — for every one of those, the interface waits for authoritative backend confirmation. This restates, and never weakens, DS-EXE-001/DS-API-EXE-001's pipeline boundary and DS-SCA-012's order-authorization-trail requirement at the UI-optimism layer. The Committed/MVP baseline it extends is DS-UX-016 (Interface State Lifecycle, §14); DS-BL-027 itself is a backlog entry, not yet a promoted DS-007 requirement.

## 10. User Journeys

Every flow below is a **derived summary** (§2): the requirements it cites remain the authoritative source of any individual obligation; the flow narrative itself creates no new requirement.

**Onboarding and local setup.** First launch routes a no-prior-profile user to onboarding (DS-USR-001, Planned); the app requires no network access to reach a usable local workspace (DS-OPS-004, Committed/MVP; DS-USR-001 edge case). Startup budgets: 10s cold / 3s warm on reference hardware (DS-NFR-001, Committed/MVP).

**Creating a watchlist.** User adds symbols to a named, persistent Watchlist (DS-MKT-007, Planned); duplicate additions are no-ops; a delisted entry is flagged, not silently removed.

**Running a scanner.** Deterministic pre-filtering runs before any AI step (DS-SCN-001, Committed/MVP); results are ranked and explainable on request (DS-SCN-003, Committed/MVP); an optional AI-assisted layer (DS-SCN-004, Planned) operates only on the already-filtered set.

**Reviewing a signal.** A Signal (DS-SIG-001, Committed/MVP) carries its grade (DS-SIG-002, Committed/MVP, deterministically derived — never unstructured AI judgment alone) and its full evidence/reasoning.

**Opening a trade assessment / exploring why-trade / why-not-trade.** Every accepted or rejected signal exposes its reason set from the fixed vocabulary (DS-SIG-003, Committed/MVP) without leaving the surface (DS-UX-009, Committed/MVP for this Signal surface). This is DarkSage's Explainability-First presentation pattern (DS-001 §15) instantiated concretely.

**Creating a paper Trade Proposal.** A Trade Proposal (DS-EXE-002/DS-API-EXE-005, Planned, Phase 7) is created as a structured, advisory-only object — creation alone never submits an order, never reaches the Broker Adapter, and confers no execution authority regardless of whether Sage or the user authored it (DS-PRD-005, "Sage advises. The user decides.").

**Canonical validation.** Submitting the proposal (DS-API-EXE-006, Planned) requires a distinct, explicit, separately-authorized user confirmation — no Sage action and no prior API call can itself constitute that confirmation — and enters the full canonical `TradeValidationPipeline` (§11) at its first stage, proceeding through every stage in order with no skip, reorder, or shortcut.

**Receiving a rejection/block.** A pipeline stage failure (e.g., Risk Engine) returns the failing stage and reason, never a generic/opaque failure (DS-API-EXE-006); the block is never overridable by Sage narration or instruction (DS-RSK-001, DS-SGE-006).

**Running a backtest.** Deterministic, reproducible given identical strategy/data/config (DS-BKT-001, Planned); realistic non-zero cost/slippage assumptions by default (DS-BKT-002); the "not a guarantee of future performance" disclosure is present on every result (DS-BKT-004).

**Comparing strategies.** Segmented performance (DS-PERF-002, Planned) prevents a strategy from being judged only in aggregate; small-sample segments are disclosed as low-confidence, never weighted equally with well-sampled ones.

**Journaling a trade.** **Non-committed roadmap direction without dedicated requirement or DS-013 backlog authority** — see §9.14. No committed or Planned journal requirement currently exists to describe here beyond `ROADMAP.md` Phase 7's directional mention.

**Asking Sage for explanation.** Once Sage exists (Planned, Phase 6), it answers the DS-001 §15 explainability question set on request (DS-SGE-013), distinguishes evidence from inference (DS-SGE-001), and abstains or communicates uncertainty rather than fabricating confidence when evidence is insufficient (DS-SGE-002) — all unconditionally bound by the already-Committed DS-PRD family regardless of DS-AI/DS-SGE's own Planned classification.

**Configuring an AI provider.** Settings > AI Providers (Planned, Phase 6) supports add/test/edit/disable/remove for provider credentials; a stored key is never redisplayed in full once saved (DS-ARC-015, Committed/MVP, fixed now even though the UI itself is Planned).

**Mobile alert and approval flow.** Once mobile exists (Planned, Phase 9), it observes identical backend-authoritative Auto-Trader/account state to desktop at the same point in time (DS-ARC-003) and can trigger backend state changes (e.g., stop Auto-Trader) but never independently compute or hold canonical trading state (DS-MOB-002, Committed/MVP governance boundary fixed now).

**Emergency Stop.** Reachable from any authorized client, independent of the normal order-submission code path, so a partial system failure that would justify triggering it does not also disable it (DS-EXE-004/DS-ARC-022, Planned Phase 7 implementation, acceptance fixed now): blocks all new orders immediately, cancels pending entry orders, continues monitoring existing positions. Must be easier to trigger than to enable live trading.

**Emergency Flatten.** A stronger, more dangerous control: blocks new orders, cancels open orders, closes active positions per emergency rules; requires strong authentication in live mode (DS-EXE-005, DS-SCA-007/016).

**Offline/stale-state behavior.** Local-only capability remains usable when network/external services are unavailable (DS-OPS-004, Committed/MVP); every value carries its data-state label throughout (DS-PRD-008); the DS-UX-016 Interface State Lifecycle (§14) governs the exact Loading/Ready/Refreshing/Degraded-Partial/Error/Retry-Recovery transitions every surface follows.

Every flow above preserves the authoritative backend and safety boundaries stated in §11 without exception.

## 11. Canonical Trade and Safety Model

### 11.1 The Canonical `TradeValidationPipeline`

This is the exact, normalized 12-stage pipeline as defined once in `ARCHITECTURE.md` §14 and mirrored verbatim in `docs/pipeline-stages.txt` (mechanically checked by `scripts/verify-foundation.sh`). It is reproduced here in the same order, with no renaming, reordering, omission, or duplication:

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

The AI/Strategy Engine may create or explain a Trade Proposal. It has no authority to bypass any downstream stage, and no authority to directly access or call the Execution Engine or Broker Adapter under any circumstance, regardless of confidence, urgency, or which AI provider generated the proposal (`ARCHITECTURE.md` §14; DS-EXE-001, DS-API-EXE-001, both **Committed/MVP**).

### 11.2 Proposal Versus Permission

A Trade Proposal (DS-EXE-002, Planned) is a candidate trade, not yet validated. It carries the signal, strategy, and proposed size/direction. Creating a proposal (DS-API-EXE-005) never itself grants permission for anything — permission is decided only by the pipeline stages downstream of it. This is the concrete instantiation of "Sage advises; the user decides" (DS-001 §12) at the execution layer.

### 11.3 Quality Versus Probability

A Signal's grade (DS-SIG-002, deterministic, never AI-judgment-only) and a setup's contextual quality score (DS-ARC-025, Planned) describe the *quality* of a candidate. Neither is a probability of success, and neither is itself trade eligibility (§9.6/§9.7).

### 11.4 Eligible Versus Executable

A pattern detection, setup-quality score, or signal grade may make a candidate *eligible for consideration* — it never makes it *executable*. Executability is decided exclusively by the pipeline (`TRADING_RULES.md` "Pattern Detection Is Not a Trade Signal").

### 11.5 Advisory Versus Authoritative

Sage — and every AI provider, local or cloud, regardless of vendor — is advisory only. The Risk Engine, Permissions Engine, and every downstream pipeline stage are authoritative and independently enforceable (DS-RSK-001, DS-PRD-006, ADR-002, all **Committed/MVP**). No external caller, including a future Sage, can modify, bypass, disable, silently override, or substitute for the Risk Engine.

### 11.6 Fail-Closed Conditions

Per `SECURITY_RULES.md` "Fail Closed" and DS-SCA-001/DS-SCA-015 (both **Committed/MVP**): whenever critical uncertainty exists — authentication unavailable, market data stale, broker mismatch, Risk Engine failure, database inconsistency, Permissions Engine unavailable — the system blocks new trades rather than guessing. When convenience conflicts with protection of user money, credentials, trading authority, or account access, protection takes priority.

### 11.7 Paper-First Progression

Per DS-RM-006 (DS-011, **Committed/MVP**), DarkSage progresses through the strict Gate-chain: **Phase 7 (Paper Auto-Trader) → Phase 8 (Shadow Trading and Strategy Tournament) → Phase 12 (Production Hardening) → Phase 13 (Limited Live Trading) → Phase 14 (Full Live Platform).** No development agent may enable real-money trading; execution work targets simulation, shadow, or paper trading until the explicitly approved live phase. Phases 9 (Mobile), 10 (Advanced Research), and 11 (Options Research) are Parallel/Optional tracks — they neither gate nor are gated by this sequence.

The product-level strategy-promotion progression (`TRADING_RULES.md` "Strategy Promotion") is: **Experimental → Backtest → Validation → Out-of-sample → Walk-forward → Shadow → Paper Auto-Trading → Limited Live → Approved Live.** Strategies may be demoted automatically if performance deteriorates.

### 11.8 Emergency Controls

See §10 "Emergency Stop"/"Emergency Flatten" above (DS-EXE-004/005). Both remain reachable independent of the normal order-submission code path so a partial system failure does not also disable them.

### 11.9 Loss Lockouts

Per `TRADING_RULES.md` "Risk Rules" and DS-RSK-001–003: maximum risk per trade, maximum daily/weekly loss, maximum position size, maximum open positions, sector/correlated-exposure limits, portfolio risk budget, strategy drawdown limits, liquidity/spread/volatility constraints, and event-risk rules are all enforced by the Risk Engine and cannot be bypassed by any caller.

### 11.10 No AI Bypass (restated)

No AI provider — local or cloud, any vendor — may communicate directly with a broker or bypass the canonical `TradeValidationPipeline` (`SECURITY_RULES.md` "AI Privacy and Provider Credentials"). No provider may directly access or call the Execution Engine or Broker Adapter. This applies identically regardless of vendor, and identically before and after user confirmation of a proposal (DS-SGE-005).

### 11.11 Live Trading Gate

DS-EXE-007 (**Committed/MVP** governance boundary; Planned implementation, Phase 13) fixes now that live trading shall not be enabled until, at minimum: (1) paper performance is acceptable per defined strategy-promotion requirements; (2) an independent security review has passed; (3) broker reconciliation has passed; (4) the kill switch (Emergency Stop/Flatten) has passed testing; (5) data-health checks have passed; (6) duplicate-order prevention has passed; (7) monitoring is active; (8) the user has explicitly and separately unlocked live trading. No AI agent, background process, or automated tooling can flip the live-trading flag — only an explicit, authenticated user action can.

## 12. Data and Provider Requirements

- **Provenance:** DS-PRD-002 (Committed/MVP) — material Sage conclusions traceable to contributing evidence, calculations, model outputs, and timestamps, where technically feasible.
- **Freshness:** DS-MKT-004 (Committed/MVP) — 10s / delay+60s / 1hr thresholds (§9.2).
- **Quality checks:** DS-QA-012 (feed-interruption simulation); `TRADING_RULES.md` "Data Integrity" (missing candles, stale quotes, provider outages, invalid prices, broken timestamps, suspicious volume, corrupt corporate-action adjustments all pause trading when uncertain).
- **Timestamps / point-in-time data:** DS-BKT-003 (Planned) — no simulated decision may access data with a knowledge timestamp later than the simulated time; DS-API-COR-002 (Committed/MVP) — ISO-8601 UTC timestamps required wherever data state is surfaced.
- **Provider abstractions:** DS-ARC-006 (Committed/MVP, market data), DS-EXE-006 (Planned, Phase 7, broker), DS-ARC-013 (Planned, Phase 6, AI) — every provider category sits behind a common interface so consuming code never depends on a vendor-specific SDK.
- **Conflicting providers:** DS-SGE-009 (Planned) — Sage discloses genuine evidence conflicts rather than silently preferring one source.
- **Outage behavior:** DS-AI-006/DS-SGE-019 (Planned) — three distinct disclosed states (normal/degraded/unavailable); DS-OPS-004 (Committed/MVP) — local-only capability remains usable regardless of external outage.
- **Free/public-first where reliable:** `PROJECT_SPEC.md` §2.1 Cheap-First Architecture — deterministic local code, then local AI, then free API tiers, then paid APIs only when proven necessary.
- **Licensing and data rights:** No Codex requirement currently commits a specific data-vendor licensing decision; DS-BLG-004's Market-Data Licensing review-gate flag governs any future provider addition (DS-013, non-committed process gate).
- **No vendor lock-in:** DS-PRD-001 (Committed/MVP) — no Committed/MVP capability may architecturally depend on one AI/model vendor without an ADR; DS-ARC-019 (Committed/MVP) — no tight coupling between market-data providers and core models.

## 13. Sage Requirements

**Local-first:** DS-ARC-014 (Planned) — local AI is the default and preferred provider; the application functions fully with zero cloud AI providers configured.

**Optional provider selection:** DS-ARC-013 (Planned) — a common `complete()`/`chat()`/`stream()` interface across local and cloud (OpenAI, Anthropic, Google Gemini, custom OpenAI-compatible endpoints); per-feature provider/model selection (Sage chat, deep signal analysis, research/news summaries, strategy explanations) configured in the backend, never the client.

**Advisory role:** DS-003 Core Rule — "Sage advises. The user decides." Sage shall not bypass the Risk Engine, conceal material risk, or present unsupported certainty; it may propose and explain a trade, never submit an order or access/call the Execution Engine or Broker Adapter, under any circumstance.

**Explanations:** DS-SGE-013 (Planned) — answers DS-001 §15's eight explainability questions (why this conclusion, what evidence, how strong/current, what uncertainty, what risks, what assumptions, what would invalidate it, what changed) on request, using a consistent internal structure.

**Research synthesis:** DS-AI-002/DS-SGE-007 (Planned) — evidence access independent of workspace presentation (ADR-004); a documented, disclosable evidence-weighting methodology.

**Tutoring:** DS-EDU-001 (Planned)/DS-EDU-002 (Future/Exploratory) — Trading Education mode content delivery is advisory only and never replaces deterministic detection or scoring in the Knowledge Engine.

**Contradictions:** DS-SGE-009 (Planned) — conflicting evidence disclosed, never silently resolved.

**Abstention:** DS-SGE-002 (Planned) — when evidence is insufficient for a confident conclusion, Sage communicates uncertainty or abstains rather than fabricating confidence; `TRADING_RULES.md` "AI Abstention" — no trade, insufficient confidence, conflicting evidence, and more-data-required are all valid Sage outputs.

**Deterministic boundaries:** DS-SGE-003 (Planned) — Sage never presents a language-model-generated numeric/factual claim as the output of a deterministic calculation; ADR-003/DS-PRD-004 (Committed/MVP) remain absolute regardless of Sage's own classification.

**Memory status:** Session-scoped memory (DS-SGE-010, Planned) is the only current/Planned memory capability. **Persistent, cross-session Sage Memory (DS-SGE-012) is explicitly Future/Exploratory** — not part of current Committed/MVP or Planned scope, and requires a dedicated privacy/consent review before any promotion.

**Third-party model gates:** Per DS-IDG-004 (DS-014, Committed governance rule), any named external model/reference (e.g., Kronos, cited only as a research reference) requires all nine mandatory gates — licensing, independent benchmarking, compute requirements, privacy, security, model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, operational feasibility — satisfied and recorded before any promotion beyond DS-014's research stage.

**Privacy and credential behavior:** DS-ARC-015/DS-SCA-003 (Committed/MVP) — provider API keys never committed, logged, or exposed in frontend/client source; local and cloud AI receive no credentials or unnecessary sensitive account data; DS-SGE-011 (Planned) — any Sage memory retains only what is justified by active use and excludes raw credentials/secrets.

## 14. UI/UX Requirements

- **Navigation/hierarchy:** DS-UX-002 (Committed/MVP, Phase-1 shell), DS-UX-018 (Committed/MVP, desktop-first mouse-and-keyboard interaction per ADR-001).
- **Presentation Independence:** DS-UX-001 (Committed/MVP) — no client code path may ever use "is widget X visible" as input to a capability-gating decision; restoring a hidden widget never requires a separate re-enable action.
- **Accessibility:** DS-UX-017/DS-NFR-004 (Planned) — WCAG 2.2 Level AA cited as an example target (formal adoption remains an owner decision); every Committed/MVP workflow keyboard-operable; status never conveyed by color alone.
- **Charts:** DS-UX-013 (Committed/MVP) — cross-engine value parity; insufficient lookback data disclosed, not silently rendered misleading.
- **Responsive layouts, desktop and mobile:** DS-UX-018 (desktop, Committed/MVP) and DS-UX-020 (mobile parity boundary, Planned, Phase 9) — no client/platform may silently gain execution authority merely by existing on a different platform.
- **Loading / skeleton / empty / partial / stale / offline / failure / retry / pending / accepted / rejected / timed out — the Interface State Lifecycle (DS-UX-016, Committed/MVP):**

  | Transition | Rule |
  |---|---|
  | Loading → Ready | Successful initial fetch, complete data |
  | Loading → Error | Initial-fetch failure, no prior data to fall back to |
  | Ready → Refreshing | Background/user-initiated refresh; previously valid data stays visible/interactive where safe |
  | Refreshing → Ready | Successful refresh, complete/current data |
  | Refreshing → Degraded/Partial | Incomplete data or mid-refresh degradation; unaffected portion stays visible, affected portion clearly marked |
  | Degraded/Partial → Ready | Subsequent successful refresh restores complete/current data |
  | Any state → Error | Unrecoverable failure |
  | Error → Retry/Recovery | User- or system-initiated retry |
  | Retry/Recovery → Loading or Refreshing | Never jumps directly to Ready without a fetch attempt |

  No surface presents Loading/Refreshing/Degraded-Partial/Error data with the same visual/textual treatment as Ready data. Non-visual (assistive-technology) announcement of these transitions is a **separate Planned obligation** (DS-UX-022) — not itself a Committed/MVP acceptance criterion of DS-UX-016.

- **Tooltips:** Governed only at the backlog level (DS-BL-027, Approved Future, §9.22) — contextual tooltips for indicators, scores, and unfamiliar terminology, building on DS-EDU-001 where applicable; not yet a promoted DS-007 requirement.
- **Caching and safe optimistic rendering:** DS-BL-027's Hard Safety Boundary (§9.22) applies without exception — optimistic rendering permitted only for low-risk, reversible actions (watchlist changes, layout preferences, filters, notes); prohibited outright for trades, broker actions, risk/permission changes, Emergency Stop/Flatten, credentials, authentication, and strategy promotion.

## 15. Nonfunctional Requirements

| Category | Requirement | Governing ID | Class. |
|---|---|---|---|
| Performance | Cold start ≤10s / warm start ≤3s on defined reference hardware (quad-core 2018+, 8GB RAM, SSD, Windows 10/11 or equivalent) | DS-NFR-001 | **Committed/MVP** |
| Responsiveness | Documented maximum latency budget per common interactive operation, regression-tracked | DS-NFR-002 | Planned |
| Scalability | Not separately specified as a numeric target in the current Codex — **TBD/open**, not guessed here | — | — |
| Concurrency | Not separately specified as a numeric target — **TBD/open** | — | — |
| Reliability | Crash/forced-termination recovery with no loss of previously saved data; termination event logged | DS-NFR-003 | **Committed/MVP** |
| Availability | Governed by DS-OPS-004 (offline/degraded operation) rather than an uptime SLA — no numeric target exists for the current local-first deployment stage | DS-OPS-004 | **Committed/MVP** |
| Maintainability | Extension points (new provider/widget) achievable without editing unrelated families' behavior | DS-NFR-005 | Planned |
| Portability | Governed structurally by DS-ARC-001/019 (client/server separation, no tight coupling) rather than a distinct portability metric | DS-ARC-001/019 | **Committed/MVP** |
| Testability | Every Committed/MVP requirement has ≥1 recorded automated/manual test | DS-NFR-006 | **Committed/MVP** |
| Accessibility | WCAG 2.2 Level AA cited as example target; formal adoption pending owner decision | DS-NFR-004/DS-UX-017 | Planned |
| Security | See §16 | DS-008 (DS-SCA family) | Mixed |
| Privacy | Data minimization, justified external-service use | DS-SEC-002/003 | **Committed/MVP** |
| Auditability | See §9.21 | DS-OPS-001/002, DS-SCA-020/025/027 | **Committed/MVP** |
| Observability | Material events, security-sensitive actions, Risk Engine/Sage-affecting determinations logged | DS-DEV-023 | **Committed/MVP** |
| Backup and recovery | Documented backup/recovery procedure for critical local data categories | DS-SCA-010 | **Committed/MVP** |
| Deterministic reproducibility | Fixed input fixtures reproduce identical output byte-for-byte (or within defined float tolerance) across runs | DS-PRD-004, DS-QA-004/005 | **Committed/MVP** |
| Data retention | User-configurable retention for non-authoritative history; authoritative records never silently pruned | DS-DAT-004 | Planned |

No numeric performance/scalability/concurrency/availability target is invented beyond what the sources above already state; every unapproved target is marked **TBD/open** rather than guessed, per this document's quality rules (§below).

## 16. Security and Privacy

- **Threat boundaries:** DS-SCA-023 (Committed/MVP) — seven trust boundaries (desktop↔backend, backend↔database, backend↔broker/provider adapters, Sage/model runtime↔deterministic services, local storage↔application process, update mechanism↔installed application, paper-trading↔live-trading boundary), each enforced backend-side, never client-side-only.
- **Credentials:** DS-SEC-001/DS-SCA-002 (Committed/MVP) — never committed, logged, or exposed; production credentials use OS-appropriate secure storage or an encrypted vault.
- **Least privilege:** `SECURITY_RULES.md` "Least Privilege"/DS-SCA-013 (Planned, Phase 7) — DarkSage shall never require withdrawal permission, external money transfers, or account-ownership changes.
- **Separate paper/live credentials:** DS-SCA-013 (Planned, Phase 7) — paper and live credential storage never share the same stored secret or configuration entry.
- **No withdrawal permission:** restated identically in `TRADING_RULES.md` "Broker Permissions" and `SECURITY_RULES.md` "Least Privilege" (Committed governance principle, Planned Phase-7 implementation).
- **Strong authentication:** DS-SCA-007 (Committed/MVP governance boundary; Planned implementation) — enabling live trading, changing live broker credentials, increasing major risk limits, Emergency Flatten, and re-enabling trading after a security event all require strong authentication.
- **Remote-action controls:** DS-SCA-006 (Committed/MVP) — security decisions enforced on the backend only; a UI-only control is never sufficient; adversarial bypass via direct API call must be independently rejected by the backend.
- **Logs:** DS-SCA-020 (Committed/MVP) — see §9.21; no log entry ever contains a full secret.
- **Audit integrity:** DS-SCA-025/027 (Committed/MVP) — append-only architecture plus deterministic verification contract; see §9.21.
- **Model supply chain / untrusted artifacts:** DS-IDG-004 (DS-014, Committed governance rule) — any downloaded model file or weight checkpoint is treated as untrusted input until verified, per `SECURITY_RULES.md` "Input Validation" extended to binary model artifacts.
- **Provider privacy:** DS-SCA-003 (Committed/MVP) — local and cloud AI receive no credentials or unnecessary sensitive account data.
- **Incident response:** DS-SCA-026 (Committed/MVP) — a fixed 10-step lifecycle (Detection → Classification/Severity → Containment → Session/Credential Revocation → Trading Disablement/Fail-Closed → User Notification → Evidence Preservation → Recovery/Remediation → Validation Before Re-Enabling → Post-Incident Review); **Step 9 is never skipped for a live-trading-relevant incident, regardless of severity classification.**
- **Local versus hosted boundaries:** DS-ARC-018 (Committed/MVP) — Stage 1 (local, $0/month) through Stage 4 (live trading, hardened); Stage 3/4 not committed to current scope.

## 17. Testing and Acceptance

- **Requirement coverage:** DS-QA-001/DS-NFR-006 (Committed/MVP) — every Committed/MVP requirement across DS-002–DS-008 carries at least one recorded automated/manual test.
- **Unit/integration/system/E2E expectations:** DS-QA-002 (integration, adapter-substitution testing), DS-QA-003 (API contract testing, contract-first — implementation never diverges from DS-006 without DS-006 updating first), DS-QA-016 (End-to-End Workflow Testing against `ROADMAP.md` phase exit criteria).
- **Deterministic tests:** DS-QA-004/005 (Committed/MVP) — fixture-based regression suites for every material financial calculation, reproducing identical output across runs unless the calculation itself changed (recorded, not silently absorbed).
- **Pipeline tests:** DS-QA-009 — the unconditional pipeline-integrity constraint (no code path ever submits an order without passing every canonical stage in order) is Committed/MVP and testable now; the conditional Trade Proposal submission test is Planned, tied to DS-API-EXE-005/006's own Phase-7 timing.
- **Security tests:** DS-QA-013 (Committed/MVP) — authentication, authorization, secret scanning, dependency scanning, input-validation, API-abuse, rate-limit, broker-safety, and fault-injection categories.
- **Backtesting reproducibility:** DS-QA-010 (Planned, Phase 2) — deterministic reproducibility, realistic cost modeling, look-ahead-bias prevention, and the "not a guarantee" disclosure (the disclosure-presence check is itself testable now as a response-schema contract).
- **Severity precedence:** DS-QA-019 (Committed/MVP) — exactly four levels (**Critical, High, Medium, Low**); when a defect matches more than one level's criteria, the **highest-matching severity governs** — never split across records, never averaged down.
- **Release-blocking behavior:** DS-QA-017 (Committed/MVP) — a phase's `ROADMAP.md` exit criteria plus applicable DS-009 test categories must pass before the phase is recorded complete; the live-trading release gate is DS-EXE-007's exact eight-item prerequisite list (§11.11) — live trading is never enabled without every prerequisite's corresponding test passing.
- **Traceability:** DS-QA-018 (Committed/MVP) — every Committed/MVP requirement across DS-002–DS-009 maps to at least one recorded test in `docs/traceability/TRACEABILITY_MATRIX.csv`.
- **No fabricated implementation evidence:** DS-DEV-020 (Committed/MVP) — no change produced by development tooling (including AI-assisted tooling) is merged/approved based solely on the producing tool's own self-assessment; DS-QA-011's model-evaluation non-substitution rule (Planned, Phase 6) — a favorable model-evaluation score never authorizes treating generative output as a financial calculation.

## 18. Scope Classification

DarkSage's Codex uses three independent classification vocabularies that are never interchangeable, per the exact governance rules each source defines:

### 18.1 Requirement Release Classification (DS-002 §5.3)

- **Committed / MVP** — approved for the current minimum viable product; implementation-ready once dependent architecture exists.
- **Planned** — approved direction, not yet committed to current MVP scope or sequencing; becomes Committed only through an explicit roadmap decision or owner/Keeper approval, never silent reinterpretation.
- **Future / Exploratory** — non-binding aspiration; requires future dedicated requirements, risk review, and architecture approval before it may become Planned or Committed.

**Committed/MVP eligibility test:** a requirement is Committed/MVP only if traceable to (a) a DS-001 FOUNDATIONAL PRINCIPLE, (b) an approved ADR, (c) bare technical/safety necessity for an already-Committed item, or (d) explicit `ROADMAP.md` Phase 1 scope.

### 18.2 DS-013 Backlog Status Taxonomy (exactly eight, canonical)

**Approved Future, Planned, Candidate, Deferred, Blocked, Research Needed, Rejected / Not Pursuing, Promoted.** Backlog "Planned" status is a distinct concept from Release Classification "Planned" — citing one never establishes or implies the other (DS-013 §4 Definitions). Inclusion in the backlog is never itself approval for implementation (DS-BLG-001). **Promoted never means implemented, released, completed, or deployed** — it means an approved controlling authority (a dedicated DS-002+ requirement, an approved DS-011 roadmap entry, or an approved DS-012 ADR) now exists for it.

### 18.3 DS-014 Idea Status Taxonomy (exactly four)

**Exploratory, Under Active Research, Promoted, Archived / Not Pursuing.** All DS-014 content is non-committed and carries no Release Classification until formally promoted, first typically into a DS-013 backlog item, per DS-IDG-001/003.

### 18.4 Rejected / Not Pursuing

Recorded as a decision record, never deleted (DS-BLG-002's rule) — e.g., DS-BL-014 ("Military-Path / Branch-Specific Fitness Crossover Concepts," rejected as having no connection to DS-001 §4's product definition).

### 18.5 Open Owner Decisions

See §22.

**These three vocabularies do not become interchangeable across governance systems.** A backlog item's "Planned" status is never cited as evidence a requirement holds Release Classification "Planned," and an idea's "Promoted" status is never cited as evidence of product commitment beyond "a DS-013 entry now exists for it."

## 19. Roadmap Alignment

`ROADMAP.md` remains authoritative for phase content (goals, deliverables, exit criteria); DS-011 governs the classification/sequencing layer over it. Fifteen phases, 0 through 14, each with a fixed sequencing category (DS-RM-015): **Strict** (cannot begin until its Key Dependency phase(s) exit), **Parallel** (proceeds concurrently once its own Key Dependency is met), **Optional/Deferred** (Future/Exploratory content, timing not fixed beyond its Key Dependency), **Gate-chain** (part of the strict paper-first/live-later sequence).

| Phase | Purpose | Sequencing Category | Current Implementation Position |
|---|---|---|---|
| 0 — Foundation | Safe, consistent dev environment | Strict | Complete (governance/process only) |
| 1 — Core Market Intelligence | First working desktop research app | Strict | Committed/MVP baseline for most DS-002/004/005/006/007 Committed requirements — Codex specification complete; implementation status is a separate, code-level fact not asserted by this document |
| 2 — Backtesting and Strategy Lab | Prove strategy logic historically | Strict | Planned — DS-STR, DS-BKT families |
| 3 — Strategy Intelligence | Learn which strategies work where | Strict | Planned — DS-PERF family |
| 4 — Portfolio Builder | Long-term investing/portfolio intelligence | Parallel (with 2/3) | Planned — DS-PRT family |
| 5 — Pattern Recognition/Advanced Charts/Knowledge Engine | Visual/structured technical intelligence | Parallel | Mixed — DS-EDU-001/DS-ARC-025 Planned; DS-EDU-002 Future/Exploratory |
| 6 — Local AI, Cloud Providers, Sage | AI assistance without authority | Parallel | Planned — DS-AI, DS-SGE families (safety boundaries Committed regardless of phase) |
| 7 — Paper Auto-Trader | Execute approved strategies in paper mode | Strict; first Gate-chain phase | Planned implementation; pipeline governance boundary Committed now |
| 8 — Shadow Trading and Strategy Tournament | Improve strategies without risking capital | Gate-chain, contingent | Future/Exploratory direction only |
| 9 — Mobile App | Control DarkSage from iPhone | Parallel | Planned — DS-MOB family |
| 10 — Advanced Research | Deeper market/portfolio intelligence | Optional/Deferred | Future/Exploratory |
| 11 — Options Research | Options as a separate instrument system | Optional/Deferred | Future/Exploratory — no live options trading in this phase |
| 12 — Production Hardening | Always-on deployment | Gate-chain | Planned |
| 13 — Limited Live Trading | Very small real-money allocations | Gate-chain | Planned; governance boundary (DS-EXE-007/DS-SCA-022) Committed |
| 14 — Full Live Platform | Mature production trading | Gate-chain | Future/Exploratory for full-auto mode; deterministic risk/permissions apply at all times |

**Paper-first, limited-live, full-live, explicit future authorization:** restated at §11.7/§11.11. No calendar date or delivery promise is stated anywhere in this section, consistent with DS-RM's own explicit non-invention rule.

## 20. Assumptions, Constraints, and Exclusions

- **Desktop first.** ADR-001 (Approved) — the primary current product direction; does not prohibit future companion clients.
- **Six-user private deployment.** No DS-001–DS-014 volume, ADR, or `ROADMAP.md` phase establishes a six-user (or any specific user-count) private-deployment requirement or commitment. Where such a deployment is discussed, it is external deployment discussion, not a product-governance question, and this document does not treat it as a controlled scope item or pending decision.
- **Market data licensing constraints.** Not yet resolved for any specific vendor beyond `PROJECT_SPEC.md` §1/§5's initial equities/S&P-500-focus direction; DS-BLG-004's Market-Data Licensing review-gate governs any future addition.
- **No guaranteed returns.** DS-001 §21 — DarkSage is not a promise of profit or a guaranteed market predictor.
- **Educational and decision-support positioning.** DS-001 §4 — a trading intelligence and decision-support platform, not a substitute for user judgment.
- **Legal/tax/current-rule verification requirements.** `TRADING_RULES.md` "Educational Knowledge Provenance" — historical or potentially outdated regulatory, tax, broker, exchange, or market-structure information must never be presented as current fact without current authoritative verification.
- **No autonomous live execution authority.** DS-PRD-007 (Committed/MVP) — autonomous trade execution remains outside approved product scope unless separately authorized through future dedicated requirements, risk review, and governance approval.
- **No fabricated implementation state.** This document, consistent with DS-DEV-020/DS-QA-019, never claims a requirement is implemented where the Codex records it as merely specified.
- **Specification-first status.** As of this document's baseline commit, the DarkSage Codex (DS-001–DS-014) is committed and complete as a specification; this PRS consolidates that specification and asserts nothing about the state of the DarkSage codebase's implementation beyond what the Codex itself states.

## 21. Traceability

This document's traceability model mirrors DS-002 §5.5's five-stage chain, restated here for the consolidated PRS: **Requirement → Design/ADR → Source → Test → Release/Change**, recorded in `docs/traceability/TRACEABILITY_MATRIX.csv`. As of this baseline, most rows record Source/Test/Release as **Pending** — this reflects the Codex's own current, honestly-recorded state (an implementation-neutral specification), not an omission by this document.

**Requirement family index:** see §9's per-area tables; the authoritative index of `DS-<DOMAIN>-NNN` families is DS-002 §7.

**Codex volume mapping:** DS-001 (foundation/philosophy) → DS-002 (product/software requirements) → DS-003 (Sage) → DS-004 (architecture) → DS-005 (database) → DS-006 (API) → DS-007 (UI/UX) → DS-008 (security) → DS-009 (testing/QA) → DS-010 (development standards) → DS-011 (roadmap) → DS-012 (ADRs) → DS-013 (backlog) → DS-014 (ideas).

**ADR mapping:** ADR-001 (Desktop-First) ↔ DS-ARC-002/003, DS-UX-018; ADR-002 (Sage Cannot Bypass the Risk Engine) ↔ DS-PRD-006, DS-RSK-001, DS-SGE-005/006; ADR-003 (Deterministic Financial Calculations) ↔ DS-PRD-004, DS-RSK-002, DS-QA-004/005; ADR-004 (Presentation Independence) ↔ DS-PRD-003, DS-UX-001, DS-WKS.

**Open implementation/test mappings:** explicitly **Pending** across the current traceability matrix — this document does not convert any Pending row to Complete.

**Conflict-resolution hierarchy** (DS-ADR-010, restated): (1) mandatory root security/trading governance and fixed-priority safety rules (`SECURITY_RULES.md`, `TRADING_RULES.md`, Risk Engine authority, deterministic financial truth, `TradeValidationPipeline` mandatory safeguards); (2) approved owner decisions within those boundaries; (3) approved ADRs; (4) approved Codex volumes/requirements; (5) implementation documentation; (6) local workflow/convenience files (`.ai-workflow/**`), never authoritative above this tier. No ADR — new, superseding, or otherwise — may weaken or override tier 1.

## 22. Open Questions

Only genuine, unresolved owner-decision items already present in approved Codex sources are listed here — no speculative question is invented to fill this section.

1. **`ROADMAP.md` phase boundaries as Codex release-scope authority** (DS-002/DS-004/DS-011 Appendix A, unchanged) — whether `ROADMAP.md` phase boundaries are the formally owner-confirmed authority for Release Classification remains an open governance-confirmation question, recorded in `.ai-workflow/BLOCKERS.md`'s Owner Decision Required section.
2. **Live brokerage/execution integration timing** (DS-002 Appendix A #2 / DS-INT-003) — whether manual, user-confirmed order placement through a connected brokerage is Committed/MVP, Planned, or Future/Exploratory for the current release remains undecided.
3. **Multi-monitor support commitment level** (DS-002 Appendix A #3 / DS-WKS-006 / DS-UX-006) — remains Future/Exploratory pending an owner decision on nearer-term commitment.
4. **Authentication token mechanism** (DS-006 Appendix A #2 / DS-SCA-004/005) — JWT vs. opaque session token vs. OAuth2 not yet decided; the session lifecycle contract itself is fixed and mechanism-agnostic.
5. **API cross-cutting mechanism choices** (DS-006 Appendix A #1/#3/#4/#5) — versioning scheme, pagination style, rate-limiting policy, and real-time transport protocol are each stated as obligations (something must exist) without a chosen mechanism.
6. **Application update/distribution mechanism** (DS-008 Appendix A #2 / DS-SCA-019) — no DS-002/DS-004 requirement yet commits a specific mechanism (e.g., Electron auto-updater vs. manual installer distribution).
7. **PostgreSQL/TimescaleDB migration trigger** (DS-004 Appendix A #1) — `ARCHITECTURE.md` §20 says TimescaleDB "only if justified" without a defined trigger condition; correctly deferred to Phase 12.
8. **Live-trading hosting provider** (DS-004 Appendix A #2, Stage 3/4) — not yet selected; correctly out of current scope.
9. **DS-004 vs. `ARCHITECTURE.md` change-control process** (DS-004 Appendix A #3) — whether `ARCHITECTURE.md` remains independently editable or becomes fully subordinate to DS-004's Codex change-control.
10. **Specialized financial-model research scope** (DS-011 Appendix A #2 / DS-RM-009) — deferred entirely to DS-013/DS-014's research track (DS-BL-018/019/020/021, DS-IDEA-001 cluster), not committed here.
11. **Kronos and market-foundation-model licensing/benchmarking** (DS-014 Appendix A #1) — entirely unresolved; DS-IDEA-002/DS-BL-020 exist specifically to track this evaluation without presupposing its outcome.

## 23. Appendices

### Appendix A — Terminology

See DS-001 §24 (Glossary) for the authoritative source. Key terms: DarkSage; The DarkSage Codex; Sage; User authority; Deterministic financial truth; Presentation independence; Workspace Studio; Trading Knowledge Engine; Current product direction; Future aspiration.

### Appendix B — Acronyms

| Acronym | Meaning |
|---|---|
| ADR | Architecture Decision Record |
| MVP | Minimum Viable Product |
| PRS | Product Requirements Specification (this document) |
| SRS | Software Requirements Specification (DS-002) |
| API | Application Programming Interface |
| QA | Quality Assurance |
| E2E | End-to-End (testing) |
| NFR | Non-Functional Requirement |
| RSI/MACD/ATR/VWAP/ADX/OBV | Standard technical indicators (§9.5) |
| P/L | Profit and Loss |
| DNA (Strategy DNA) | Per-stock statistical performance profile (DS-PERF-003) |

### Appendix C — Classification Summary

See §18. Three vocabularies: Release Classification (Committed/MVP, Planned, Future/Exploratory); DS-013 Backlog Status (eight values); DS-014 Idea Status (four values). Never interchangeable.

### Appendix D — Canonical Pipeline

See §11.1 — the exact 12-stage `TradeValidationPipeline`, reproduced verbatim.

### Appendix E — Product Workspace Summary

See §8.

### Appendix F — Requirement-Family Map

See DS-002 §7 (authoritative index) and §9 of this document (consolidated catalog by feature area).

### Appendix G — ADR Summary

| ADR | Decision |
|---|---|
| ADR-001 | DarkSage is desktop-first while preserving future service/API extensibility. |
| ADR-002 | Sage may advise and calculate; Sage cannot bypass or silently override the Risk Engine. |
| ADR-003 | Material financial calculations shall use deterministic implementations rather than generative model output. |
| ADR-004 | Workspace layout and widget visibility shall not determine enabled analytical capability or Sage evidence availability. |

### Appendix H — Revision History

See "Revision History" above (top of this document).

## Non-Goals

Consistent with DS-001 §21 and DS-002 §9, this document does not: create independent duplicate requirement authority (§Document ID Rationale); promote any DS-013 backlog or DS-014 idea item to Committed or Planned status by consolidating it here (§9.9, §9.14, §9.22 explicitly mark non-committed content); invent a numeric performance/scalability target the Codex does not already state (§15); make a financial-return promise; or claim DarkSage's codebase implementation state — this document consolidates the Codex's *specification*, not a claim about what has been coded.

## Dependencies

All of DS-001 through DS-014, ADR-001 through ADR-004, `ROADMAP.md`, `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `TRADING_RULES.md`, `SECURITY_RULES.md`, `AGENTS.md`, and [DSF-001 — DarkSage Publication Architecture](../publication/DARKSAGE_PUBLICATION_ARCHITECTURE.md) for presentation rules.

## Risks and Constraints

- **Consolidation drift risk:** as DS-001–DS-014 evolve, this document must be revised in the same or a following change to avoid becoming a stale summary; no automated sync exists yet (a candidate follow-up for DS-010's own process documentation).
- **Compression risk:** §9's grouped-table format necessarily omits some acceptance-criteria/edge-case detail present in the source `DS-<DOMAIN>-NNN` documents; every table row cites its source ID precisely so a reader needing full detail always has an exact pointer, per this document's own interpretation rule (§2).
- **Non-existent requirement-family gaps surfaced, not filled:** §9.8 (thesis-clock), §9.14 (journal) explicitly record that no dedicated requirement family exists yet, rather than inventing placeholder acceptance criteria.

## Verification Approach

Document-level verification for this pass: exact-Codex-reference resolution (every cited `DS-<DOMAIN>-NNN`/`ADR-NNN` ID checked against its source volume), classification-terminology scan (no blending of Release Classification with DS-013/DS-014 status vocabularies), canonical-pipeline exact-order check against `docs/pipeline-stages.txt`, Sage advisory-only scan, safety/risk/permission/execution-bypass scan, DS-013/DS-014 boundary scan, local-authority dependency scan (no `.ai-workflow/**` citation as authority), tool-neutrality scan, unapproved-numeric-target scan (§15), and empty-mandatory-section scan — recorded in `.ai-workflow/HANDOFF.md` for this task.

## References

- All DS-001–DS-014 volumes under `docs/codex/`
- All `ADR-001`–`ADR-004` under `docs/codex/Volume-12-ADRs/`
- `ROADMAP.md`, `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `TRADING_RULES.md`, `SECURITY_RULES.md`, `AGENTS.md`
- `docs/pipeline-stages.txt`, `scripts/verify-foundation.sh`
- `docs/traceability/TRACEABILITY_MATRIX.csv`, `docs/traceability/README.md`
- [DSF-001 — DarkSage Publication Architecture](../publication/DARKSAGE_PUBLICATION_ARCHITECTURE.md)
