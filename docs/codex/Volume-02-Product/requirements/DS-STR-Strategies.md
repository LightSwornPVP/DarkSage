# DS-STR — Strategies (Forge)

| Field | Value |
|---|---|
| Document ID | DS-STR |
| Title | Strategies |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Themed alias: Forge (DS-001 §17).

## Requirements

### DS-STR-001 — Strategy Construction

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Let users define a trading/investment strategy as a structured, reusable object rather than an ad hoc idea.

**Description:** DarkSage shall allow users to construct a strategy from defined entry/exit rules, applicable instruments, and parameters, saved for reuse in backtesting (DS-BKT) and scanning (DS-SCN).

**Dependencies:** DS-SCN; DS-BKT; DS-PRD-007

**Acceptance Criteria:**
- A saved strategy's rules are stored in a structured, deterministic-evaluable form (not free-text only), sufficient for backtest/scan execution.
- Strategy construction does not place, schedule, or queue any live order (DS-PRD-007).
- A strategy can be edited and re-saved without losing its version history relevant to prior backtests referencing it (see DS-BKT-002).

**Edge Cases:**
- A strategy referencing an unavailable indicator/data field is flagged as incomplete/invalid rather than silently accepted.

**Implementation Notes:** DS-004 concern for the strategy definition schema/engine.

**Testing:** Strategy construction and validation regression test with valid and invalid rule fixtures.

### DS-STR-002 — Strategy Validation

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Catch structurally broken or nonsensical strategies before a user wastes time backtesting them.

**Description:** DarkSage shall validate a strategy's structural integrity (referenced fields exist, parameters within allowed ranges, no contradictory rules) before it can be executed in a scan or backtest.

**Dependencies:** DS-STR-001

**Acceptance Criteria:**
- An invalid strategy is blocked from execution with a specific, actionable validation error, not a generic failure.
- Validation runs automatically on save and on demand before execution.

**Edge Cases:**
- A strategy valid at save time but referencing data later removed (e.g., a deprecated indicator) is re-validated and flagged at next execution attempt.

**Implementation Notes:** DS-004 concern.

**Testing:** Validation-error regression test across a fixture set of invalid strategy configurations.

### DS-STR-003 — AI-Assisted Strategy Authoring

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Let Sage help users articulate a strategy idea in structured form without becoming the authority on its validity.

**Description:** DarkSage should allow Sage to assist a user in drafting a strategy's structured rules from a natural-language description, subject to the same validation (DS-STR-002) and user confirmation before saving.

**Dependencies:** DS-STR-001; DS-STR-002; DS-PRD-005; DS-AI

**Acceptance Criteria:**
- A Sage-drafted strategy is presented to the user for explicit review/confirmation before being saved as an executable strategy.
- Sage-drafted strategies pass through the same validation as manually authored ones (no bypass).

**Edge Cases:**
- Sage's draft that cannot be structurally represented is disclosed as such rather than silently simplified into a misleading rule set.

**Implementation Notes:** DS-003 concern for the drafting interaction.

**Testing:** Draft-then-confirm workflow test; validation-parity test against manually authored strategies.
