# DS-PRT — Portfolio (Treasury)

| Field | Value |
|---|---|
| Document ID | DS-PRT |
| Title | Portfolio |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Themed alias: Treasury (DS-001 §17).

## Requirements

### DS-PRT-001 — Position Tracking

**Priority:** Critical | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Maintain an accurate record of what the user holds.

**Description:** DarkSage shall track user positions (symbol, quantity, cost basis) derived from recorded transactions (DS-PRT-002), reflecting corporate actions (DS-MKT-006) where applicable.

**Dependencies:** DS-PRT-002; DS-MKT-006; DS-PRD-004

**Acceptance Criteria:**
- Position quantity and cost basis are computed deterministically from the recorded transaction history.
- A corporate action affecting a held position (e.g., a split) updates position quantity/cost basis consistently with DS-MKT-006.

**Edge Cases:**
- A position reduced to zero remains queryable in transaction history rather than disappearing without record.

**Implementation Notes:** DS-004/DS-005 concern.

**Testing:** Position-derivation regression test against fixture transaction sequences including a corporate action.

### DS-PRT-002 — Transaction Recording

**Priority:** Critical | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Provide the authoritative, immutable record that positions and performance derive from.

**Description:** DarkSage shall allow users to record transactions (buy, sell, and other Committed/MVP transaction types) manually or via import (DS-DAT), storing each transaction immutably once confirmed.

**Dependencies:** DS-DAT; DS-PRT-001

**Acceptance Criteria:**
- A confirmed transaction is immutable; corrections are made via an explicit, logged reversing/adjusting entry, not silent edits.
- Manual transaction entry validates required fields (symbol, quantity, price, date) before confirmation.

**Edge Cases:**
- An imported transaction that fails validation is rejected individually with a specific reason, not silently dropped from a batch import.

**Implementation Notes:** DS-004/DS-005 concern.

**Testing:** Transaction entry/import regression test including an invalid-record fixture.

### DS-PRT-003 — Realized and Unrealized Performance

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Give users an accurate, deterministic view of how their holdings have performed.

**Description:** DarkSage shall compute realized and unrealized profit/loss per position and in aggregate, using deterministic calculations per DS-PRD-004 and current/last-known market data per DS-PRD-008.

**Dependencies:** DS-PRT-001; DS-PRD-004; DS-PRD-008

**Acceptance Criteria:**
- Realized P/L reflects only closed/reduced positions from recorded transactions; unrealized P/L reflects open positions marked to current or last-known price with its data state disclosed.
- Performance figures are reproducible from stored transactions and the market data snapshot used.

**Edge Cases:**
- Unrealized P/L computed against stale/delayed data discloses that state (DS-PRD-008) rather than presenting it as current.

**Implementation Notes:** DS-004/DS-005 concern.

**Testing:** Deterministic P/L regression test against fixture transaction/price data.

### DS-PRT-004 — Portfolio Overview

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Give users a single, trustworthy summary view of their holdings.

**Description:** DarkSage shall provide a portfolio overview surface aggregating positions, performance (DS-PRT-003), and material risk indicators (DS-RSK) sourced from their respective authoritative calculations.

**Dependencies:** DS-PRT-001; DS-PRT-003; DS-RSK-002

**Acceptance Criteria:**
- Every figure shown in the overview traces to its authoritative calculation (position/performance/risk engine), not a separately computed duplicate.
- The overview reflects the current data state per DS-PRD-008.

**Edge Cases:**
- A position with a calculation error (e.g., missing price) is flagged in the overview rather than silently omitted or shown as zero.

**Implementation Notes:** DS-007 concern for presentation.

**Testing:** Overview consistency test confirming figures match their source calculations exactly.

### DS-PRT-005 — Portfolio Intelligence

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall support explainable diversification, concentration, correlation, sector/factor exposure, risk-budget, scenario stress, income projection, allocation, rebalancing, and strategy-contribution analysis as data and approved models permit.

**Acceptance Criteria:** Recommendations expose assumptions, tax limitations, risk effects, and deterministic calculations; unavailable data produces a disclosed limitation rather than false completeness.
