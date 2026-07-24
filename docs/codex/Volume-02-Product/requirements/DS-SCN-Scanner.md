# DS-SCN — Scanner (Watchtower)

| Field | Value |
|---|---|
| Document ID | DS-SCN |
| Title | Scanner |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Themed alias: Watchtower (DS-001 §17).

## Requirements

### DS-SCN-001 — Deterministic Pre-Filtering

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 ("Ranking/scoring pipeline," "Candidate filtering"); `PROJECT_SPEC.md` §5.

**Purpose:** Keep scanning fast and cost-efficient by narrowing the candidate universe deterministically before any expensive AI analysis runs, consistent with DS-001 §9's restraint principle.

**Description:** DarkSage shall apply deterministic, rule-based pre-filtering (price, volume, technical, fundamental, or user-defined criteria) to the scan universe before any AI-assisted analysis step is invoked for a given scan.

**Dependencies:** DS-PRD-004 (deterministic calculations); DS-PRD-001 (model independence); DS-MKT-001

**Acceptance Criteria:**
- A scan's deterministic filter criteria are evaluated and applied before any AI-model call is made for that scan.
- Filter criteria and their evaluated results are inspectable by the user (which symbols passed/failed and why).
- A scan configured with zero AI-assisted steps still functions correctly using deterministic filtering alone.

**Edge Cases:**
- A filter criterion referencing unavailable data (e.g., a fundamental field not present for a symbol) excludes that symbol with a disclosed reason rather than silently passing or failing it.

**Implementation Notes:** Filter rule engine design is a DS-004 concern.

**Testing:** Filter-only scan regression test (no AI step invoked) verifying correct candidate narrowing.

### DS-SCN-002 — Scan Configuration and Execution

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 ("Initial stock universe," "S&P 500-focused scanner," "Scanner presets"); `PROJECT_SPEC.md` §5.

**Purpose:** Let users define and run repeatable scans over their chosen universe.

**Description:** DarkSage shall allow users to configure, save, and execute scans consisting of a symbol universe (e.g., watchlist, market, index), deterministic filter criteria (DS-SCN-001), and optional ranking/scoring (DS-SCN-003).

**Dependencies:** DS-SCN-001; DS-MKT-007 (watchlists); DS-USR-002 (persistence)

**Acceptance Criteria:**
- A saved scan configuration re-executes with the same criteria against current data on demand.
- Scan execution reports which symbols were evaluated, which passed, and why, at minimum on request.
- A scan against an empty or unavailable universe completes with a clear empty-result state rather than an error.

**Edge Cases:**
- A scan universe that changes between saves (e.g., index membership change) is evaluated against the current membership at run time, with the change disclosed if material.

**Implementation Notes:** DS-004/DS-007 concern for execution/UI.

**Testing:** Scan save/execute regression test; empty-universe test.

### DS-SCN-003 — Ranking and Scoring

**Priority:** Medium | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 ("Ranking/scoring pipeline"); exit criterion "Scanner ranks candidates."

**Purpose:** Help users prioritize scan results without presenting an opaque, unexplained ordering.

**Description:** DarkSage shall rank or score scan results using criteria disclosed to the user, distinguishing deterministic scoring components from any AI-assisted scoring components per DS-PRD-009.

**Dependencies:** DS-SCN-001; DS-PRD-009 (uncertainty communication); DS-PRD-002 (evidence provenance)

**Acceptance Criteria:**
- A result's rank/score is explainable on request: which criteria contributed, and their relative weight or role.
- AI-assisted scoring components are labeled as such and are not presented with the same certainty as deterministic components (DS-PRD-009).
- Ranking is stable and reproducible for identical input data (deterministic components) or discloses its non-determinism (AI-assisted components).

**Edge Cases:**
- Ties in ranking are resolved by a documented, deterministic tiebreak rule rather than arbitrary/unstable ordering.

**Implementation Notes:** Scoring model detail belongs to DS-003/DS-004.

**Testing:** Rank-explanation test; tie-break determinism test.

### DS-SCN-004 — AI-Assisted Scan Analysis

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Allow Sage to add synthesis/explanation value to scan results that survive deterministic pre-filtering, without becoming the scan's primary filtering mechanism.

**Description:** DarkSage should allow an optional AI-assisted analysis step to run on the deterministically pre-filtered candidate set (DS-SCN-001), providing synthesis, contextual explanation, or qualitative flags, subject to DS-PRD-001, DS-PRD-002, and DS-PRD-009.

**Dependencies:** DS-SCN-001; DS-AI; DS-PRD-001; DS-PRD-002; DS-PRD-009

**Acceptance Criteria:**
- The AI-assisted step operates only on the already-filtered candidate set, never as a substitute for deterministic filtering of the full universe.
- AI-assisted output for a scan result is labeled and distinguishable from deterministic filter/score output.
- A scan can be configured to skip the AI-assisted step entirely and still produce a complete deterministic result.

**Edge Cases:**
- AI-assisted analysis failure/unavailability degrades to the deterministic result set (DS-AI failure-behavior requirements) rather than failing the whole scan.

**Implementation Notes:** Cost/latency budget for AI-assisted analysis is a DS-004/DS-011 sequencing concern.

**Testing:** AI-step-disabled scan test; AI-step-failure degradation test.

### DS-SCN-005 — Scan Result History

**Priority:** Low | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Let users see how a saved scan's results have changed over time.

**Description:** DarkSage should retain a history of prior executions of a saved scan, including result set and timestamp, for user review.

**Dependencies:** DS-SCN-002; DS-DAT

**Acceptance Criteria:**
- Prior scan executions for a saved scan are retrievable with their timestamp and result set.
- Viewing scan history does not re-execute the scan against current data (historical results remain historical).

**Edge Cases:**
- Storage growth from frequent scan execution is bounded by a documented retention policy rather than growing unbounded by default.

**Implementation Notes:** Retention policy default is a DS-004/DS-005 concern.

**Testing:** Scan-history retrieval test confirming historical immutability.
