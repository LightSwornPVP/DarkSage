# DS-RSK — Risk Engine (Guardian)

| Field | Value |
|---|---|
| Document ID | DS-RSK |
| Title | Risk |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Themed alias: Guardian (DS-001 §17).

## Requirements

### DS-RSK-001 — Risk Engine Independent Authority

**Priority:** Critical | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Implement ADR-002/DS-PRD-006 as an enforceable engine boundary, not merely a stated policy. This boundary is unconditional and does not require Sage to exist: it constrains any current or future caller, including Sage once built (Planned, Phase 6).

**Description:** DarkSage shall implement risk rules and limits in a Risk Engine component whose rule configuration and enforcement determinations no external caller — including a future Sage — can modify, bypass, disable, silently override, or substitute itself for.

**Dependencies:** ADR-002; DS-PRD-006

**Acceptance Criteria:**
- No code path allows an external instruction (from any current or future caller) to alter a Risk Engine rule, suppress a determination, or cause the Risk Engine to be skipped for an action it would otherwise gate.
- Risk Engine determinations (blocks, limits, warnings) are logged independent of whether any other system component also produced output about the same event.
- Risk configuration changes require an explicit user/administrative action through a defined risk-configuration surface; no automated system component can make this change on the user's behalf even if asked.

**Future Enhancements (Planned, not part of this requirement's Committed/MVP scope):** Once Sage exists (DS-AI-002, DS-AI-007, Planned/Phase 6), it may query the Risk Engine, use its outputs as evidence, and explain its results to the user — read/evaluation access for advisory and evidence purposes is not itself a bypass or override. This capability is governed by DS-AI-002/DS-AI-007 and DS-SGE-006 (DS-003) when those become applicable; it is not required for this requirement's current acceptance.

**Edge Cases:**
- Risk Engine unavailability defaults to a fail-safe (block/warn) posture, not an implicit allow, for any Committed/MVP action gated by it.

**Implementation Notes:** DS-004/DS-008 own enforcement architecture.

**Testing:** Adversarial bypass-attempt test (see DS-PRD-006); fail-safe-on-unavailability test.

### DS-RSK-002 — Deterministic Position and Risk Calculations

**Priority:** Critical | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 ("Risk-engine foundation"); `TRADING_RULES.md` Risk Rules.

**Purpose:** Ensure risk metrics are trustworthy inputs to decisions, per ADR-003.

**Description:** The Risk Engine shall compute position and portfolio risk metrics (e.g., exposure, concentration, drawdown-relevant figures) using deterministic implementations per DS-PRD-004.

**Dependencies:** ADR-003; DS-PRD-004; DS-PRT

**Acceptance Criteria:**
- Given identical position and market data inputs, a risk metric reproduces identically across runs.
- Each Committed/MVP risk metric has a documented calculation method referenced from its output.

**Edge Cases:**
- Missing required input data (e.g., no volatility data for a metric) is disclosed as a calculation gap rather than defaulted to a misleading zero/neutral value.

**Implementation Notes:** DS-004/DS-005 concern for calculation-engine implementation.

**Testing:** Deterministic-output regression suite against fixture positions/market data.

### DS-RSK-003 — Risk Limits and Warnings

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Make material risk visible before it becomes a hidden surprise, per DS-001 §13.

**Description:** DarkSage shall allow users to configure risk limits/thresholds and shall surface a warning or block when a position, strategy, or scenario would exceed a configured limit.

**Dependencies:** DS-RSK-001; DS-RSK-002; DS-001 §13

**Acceptance Criteria:**
- A configured limit breach produces a warning or block (per its configured severity) visible at the point of the relevant decision, not buried in a separate report only.
- Risk warnings are not suppressed by workspace layout (DS-PRD-003).

**Edge Cases:**
- A limit breach caused by market movement (not user action) is still surfaced promptly, not only at the next user-initiated action.

**Implementation Notes:** DS-004/DS-007 concern for alerting UI (see also DS-ALT).

**Testing:** Limit-breach trigger test across configured severities.

### DS-RSK-004 — Scenario Analysis

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Help users understand downside before it happens, not only after.

**Description:** DarkSage should provide deterministic scenario analysis (e.g., hypothetical price-move impact on a position or portfolio) using the same calculation engine as DS-RSK-002.

**Dependencies:** DS-RSK-002; DS-PRD-004; DS-PRD-009

**Acceptance Criteria:**
- A scenario result is reproducible from its stated inputs/assumptions (deterministic given the scenario parameters).
- Scenario output discloses its assumptions and is not presented as a prediction of what will happen (DS-PRD-009).

**Edge Cases:**
- A scenario referencing data outside the available historical/statistical basis discloses that limitation.

**Implementation Notes:** DS-004 concern for scenario-engine design.

**Testing:** Scenario-reproducibility regression test against fixture assumptions.

### DS-RSK-005 — Risk Disclosure in Sage Output

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Prevent Sage from presenting an opportunity while omitting its material downside, per DS-001 §13.

**Description:** When Sage references a position, strategy, or recommendation with material associated risk, Sage shall disclose that risk rather than omit it to make the item appear more attractive.

**Dependencies:** DS-001 §13; DS-RSK-001; DS-AI-003

**Acceptance Criteria:**
- Sage output referencing a material opportunity includes its material downside/risk context sourced from the Risk Engine, where such risk data exists.
- Risk disclosure is not contingent on the user asking a separate question.

**Edge Cases:**
- A case where risk data is unavailable for a referenced item discloses that absence rather than implying "no risk."

**Implementation Notes:** DS-003 concern for response-composition rules.

**Testing:** Content-audit test confirming risk disclosure accompanies opportunity-framed Sage output in sampled fixtures.
