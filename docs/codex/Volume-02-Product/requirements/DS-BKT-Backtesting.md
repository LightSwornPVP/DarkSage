# DS-BKT — Backtesting (Chronicle)

| Field | Value |
|---|---|
| Document ID | DS-BKT |
| Title | Backtesting |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Themed alias: Chronicle (DS-001 §17).

## Requirements

### DS-BKT-001 — Deterministic Historical Backtesting

**Priority:** Critical | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Ensure backtest results are trustworthy calculation, not generative estimation, per ADR-003.

**Description:** DarkSage shall execute a strategy (DS-STR) against historical market data (DS-MKT-002) using a deterministic backtest engine, producing reproducible performance statistics.

**Dependencies:** ADR-003; DS-PRD-004; DS-STR-001; DS-MKT-002

**Acceptance Criteria:**
- Given identical strategy definition, historical data, and configuration, a backtest reproduces identical results across runs.
- Backtest output states the exact data range, strategy version, and configuration used to produce it.

**Edge Cases:**
- A backtest requested over a range with incomplete historical data discloses the gap and its effect rather than silently using partial data as if complete.

**Implementation Notes:** DS-004 concern for engine architecture.

**Testing:** Deterministic-reproducibility regression test against fixture strategy/data.

### DS-BKT-002 — Realistic Transaction Costs and Slippage

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Prevent backtests from overstating strategy performance by ignoring real-world trading friction.

**Description:** DarkSage shall apply configurable, disclosed assumptions for transaction costs and slippage in backtest execution, defaulting to non-zero realistic assumptions rather than a frictionless default.

**Dependencies:** DS-BKT-001

**Acceptance Criteria:**
- Default backtest configuration includes non-zero cost/slippage assumptions, disclosed in the result output.
- A user can adjust cost/slippage assumptions, and the applied values are always shown alongside results.

**Edge Cases:**
- A user who sets cost/slippage to zero is shown an explicit disclosure that the result is idealized/frictionless, not representative of achievable execution.

**Implementation Notes:** Default assumption values are a DS-004 configuration detail.

**Testing:** Cost/slippage-applied regression test comparing frictionless vs. default-assumption results on the same fixture.

### DS-BKT-003 — Look-Ahead Bias and Data Leakage Prevention

**Priority:** Critical | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Prevent a backtest from silently using information that would not have been available at the simulated decision time.

**Description:** DarkSage shall structure the backtest engine so that a strategy decision at simulated time T cannot access market or corporate-action data with an effective/knowledge timestamp later than T.

**Dependencies:** DS-BKT-001; DS-MKT-006; DS-MKT-002

**Acceptance Criteria:**
- The backtest engine enforces a hard boundary preventing any data access beyond the current simulated timestamp.
- Corporate-action data (e.g., a restated fundamental figure) uses its original knowledge date, not its data date, when determining availability at simulated time T.

**Edge Cases:**
- A data field that is itself revised after the fact (e.g., preliminary vs. final economic data) uses the point-in-time value known at T, if the underlying data source distinguishes revisions; if it does not, this limitation is disclosed.

**Implementation Notes:** Point-in-time data architecture is a DS-004/DS-005 concern.

**Testing:** Look-ahead-bias regression test using a fixture designed to detect any future-data leakage.

### DS-BKT-004 — Backtest Result Disclosure

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Prevent historical backtest performance from being mistaken for a guarantee of future results, per DS-001 §13.

**Description:** DarkSage shall accompany every backtest result with a disclosure that historical/simulated performance is not a guarantee of future performance.

**Dependencies:** DS-001 §13; DS-PRD-009; DS-PRD-008

**Acceptance Criteria:**
- The disclosure is present on every backtest result surface, including any Sage narrative summarizing the result.
- Backtest output is visually/textually distinguishable from live portfolio performance (DS-PRD-008).

**Edge Cases:** None beyond DS-PRD-008/DS-PRD-009 coverage.

**Implementation Notes:** DS-007 concern for presentation.

**Testing:** Disclosure-presence audit across backtest result surfaces.
