# DS-PERF — Strategy Performance Intelligence

| Field | Value |
|---|---|
| Document ID | DS-PERF |
| Title | Strategy Performance Intelligence |
| Version | 0.1.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Added in the DS-002-A03 repair pass to close a gap: `ARCHITECTURE.md` §11, `PROJECT_SPEC.md` §7/§8/§10, and `ROADMAP.md` Phase 3 already specify Strategy Performance Intelligence with no prior DS-002 coverage.

## Requirements

### DS-PERF-001 — Performance Metric Tracking

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §11; `PROJECT_SPEC.md` §7; `ROADMAP.md` Phase 3

**Purpose:** Give strategy evaluation more signal than win rate alone, per `TRADING_RULES.md` Core Rule #4.

**Description:** DarkSage should track, per strategy, at minimum: trade count, wins, losses, win rate, expectancy, profit factor, average win, average loss, maximum drawdown, Sharpe ratio, Sortino ratio, and sample-size confidence.

**Dependencies:** DS-BKT-001 (Planned); DS-DB-006 (DS-005)

**Acceptance Criteria:** Deferred to Phase 3 authoring; not yet testable at Planned classification.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `ARCHITECTURE.md` §11 is the authoritative metric list.

**Testing:** Not yet applicable — Phase 3.

### DS-PERF-002 — Performance Segmentation

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §11; `TRADING_RULES.md` Core Rule #8; `ROADMAP.md` Phase 3

**Purpose:** Prevent a strategy's performance from being judged in aggregate when it actually only works in specific contexts.

**Description:** DarkSage should segment strategy performance by strategy, strategy version, symbol, sector, timeframe, market regime, instrument, entry method, exit method, time of day, and day of week where relevant.

**Dependencies:** DS-PERF-001; DS-DB-003 (MarketRegime, DS-005)

**Acceptance Criteria:** Deferred to Phase 3 authoring.

**Edge Cases:** A segment with too few trades to be statistically meaningful is disclosed as low-confidence (DS-PERF-004), not presented with the same weight as a well-sampled segment.

**Implementation Notes:** `ARCHITECTURE.md` §11 is authoritative.

**Testing:** Not yet applicable — Phase 3.

### DS-PERF-003 — Strategy DNA

**Priority:** Low | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §12; `PROJECT_SPEC.md` §8; `ROADMAP.md` Phase 3

**Purpose:** Give each stock a statistically-grounded profile of which strategies/conditions historically work for it, without letting AI opinion substitute for evidence.

**Description:** DarkSage should develop a per-stock Strategy DNA profile (best/worst-performing strategies, best timeframe/regime, typical volatility, trend persistence, mean-reversion tendency, event sensitivity) based on measured statistical evidence, never AI guessing.

**Dependencies:** DS-PERF-001; DS-PERF-002

**Acceptance Criteria:** Deferred to Phase 3 authoring; the "statistical evidence, not AI guessing" constraint is fixed now per the Governing Source and applies to whatever implementation is eventually built.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `ARCHITECTURE.md` §12/`PROJECT_SPEC.md` §8 are authoritative.

**Testing:** Not yet applicable — Phase 3.

### DS-PERF-004 — Anti-Overfitting Safeguards

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `PROJECT_SPEC.md` §10; `ARCHITECTURE.md` §11; `ROADMAP.md` Phase 2–3

**Purpose:** Prevent an impressive in-sample backtest from being mistaken for a validated edge — a discipline requirement paired with DS-BKT-003's look-ahead-bias prevention.

**Description:** DarkSage should apply minimum sample-size requirements, multiple-testing protection, false-discovery warnings, parameter-stability analysis, out-of-sample validation, and walk-forward validation before a strategy may be promoted; no strategy may be promoted solely because of an impressive in-sample backtest.

**Dependencies:** DS-PERF-001; DS-BKT-001 (Planned)

**Acceptance Criteria:** Deferred to Phase 2–3 authoring.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `PROJECT_SPEC.md` §10 is authoritative.

**Testing:** Not yet applicable — Phase 2–3.
