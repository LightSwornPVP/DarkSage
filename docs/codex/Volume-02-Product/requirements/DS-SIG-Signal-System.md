# DS-SIG — Signal System

| Field | Value |
|---|---|
| Document ID | DS-SIG |
| Title | Signal System |
| Version | 0.1.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Added in the DS-002-A03 repair pass to close a material completeness gap: `PROJECT_SPEC.md` §16/§17 and `ROADMAP.md` Phase 1 already specify the Signal System and its Why-Trade/Why-Not-Trade obligation; this family formalizes it as DS-002 requirements.

## Requirements

### DS-SIG-001 — Signal Representation

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 ("Signal model"); `PROJECT_SPEC.md` §16

**Purpose:** Give Scanner output (DS-SCN, Committed) a structured, evidence-carrying representation rather than a bare ranked list.

**Description:** DarkSage shall represent each scan/strategy candidate as a Signal carrying symbol, direction, confidence, quantitative/technical/fundamental/sentiment scores where applicable, detected patterns, indicators snapshot, reasoning text, timestamp, and expiration where applicable.

**Dependencies:** DS-SCN-002, DS-SCN-003 (Committed); DS-DB-004 (DS-005)

**Acceptance Criteria:**
- Every Signal produced by a Phase-1 scan carries the fields listed above; fields not applicable to a given signal type (e.g., no strategy assigned yet) are explicitly null, not omitted silently.
- Signal reasoning text is derived from the deterministic scoring inputs that produced it (DS-PRD-004 analog), not freely generated.

**Edge Cases:**
- A signal with incomplete scoring inputs (e.g., missing fundamental data) discloses the gap rather than defaulting a score to a misleading neutral value.

**Implementation Notes:** DS-005 (DS-DB-004) defines the storage schema.

**Testing:** Field-completeness test across scan output; reasoning-derivation determinism test.

### DS-SIG-002 — Signal Grading

**Priority:** Medium | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `TRADING_RULES.md` "Signal Grades"; `PROJECT_SPEC.md` §16

**Purpose:** Give users a fast, consistent quality indicator for a signal without hiding how it was derived.

**Description:** DarkSage shall assign each Signal a grade (A+/A/B/C/D) derived from measurable inputs; a grade shall never be assigned by unstructured AI judgment alone.

**Dependencies:** DS-SIG-001; DS-PRD-004

**Acceptance Criteria:**
- Grade derivation is deterministic and reproducible from the signal's recorded scoring inputs.
- The grading methodology is documented and consistent across signal types.

**Edge Cases:**
- A signal with insufficient inputs to grade confidently is graded conservatively (lower grade) rather than defaulted to a mid-range grade.

**Implementation Notes:** Exact grading formula is a DS-004/DS-005 implementation input; this requirement mandates determinism and evidence-derivation, not the specific formula.

**Testing:** Grade-determinism regression test against fixture scoring inputs.

### DS-SIG-003 — Why-Trade / Why-Not-Trade Explanation

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `TRADING_RULES.md` Core Rules ("Why-Trade / Why-Not-Trade" — every accepted or rejected signal must include reasons); `PROJECT_SPEC.md` §17

**Purpose:** Prevent a rejected or low-graded signal from disappearing without explanation, and prevent an accepted signal from appearing without justification — a transparency guardrail, not an optional feature.

**Description:** Every Signal, whether ultimately accepted or rejected by any downstream consumer (scan filter, strategy, or future trade validation), shall carry a machine-readable reason set drawn from a defined vocabulary (e.g., poor risk/reward, weak expectancy, insufficient sample size, earnings risk, low liquidity, wide spread, market regime mismatch, sector concentration, correlated exposure, risk budget exhausted, stale data, bad data, strategy suspended).

**Dependencies:** DS-SIG-001; DS-PRD-002; `TRADING_RULES.md`

**Acceptance Criteria:**
- A rejected signal's rejection reason(s) are retrievable and drawn from the defined vocabulary, not free-text-only.
- An accepted signal's acceptance rationale references its supporting scores/evidence (DS-SIG-001).

**Edge Cases:**
- Multiple simultaneous rejection reasons are all recorded, not collapsed to a single "best" reason that hides the others.

**Implementation Notes:** DS-004/DS-005 concern for the reason-vocabulary schema.

**Testing:** Rejection-reason completeness and vocabulary-conformance test.

### DS-SIG-004 — Signal Expiration

**Priority:** Low | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `PROJECT_SPEC.md` §16 (signal "Expiration where applicable")

**Purpose:** Prevent a stale signal from being acted on as if still current.

**Description:** DarkSage should allow a Signal to carry an expiration timestamp or condition, after which it is no longer presented as actionable.

**Dependencies:** DS-SIG-001; DS-PRD-008

**Acceptance Criteria:**
- An expired signal is visually/textually distinguished from an active one (DS-PRD-008 analog).

**Edge Cases:** A signal type with no natural expiration (e.g., a long-term fundamental thesis) may omit expiration without error.

**Implementation Notes:** DS-005 concern.

**Testing:** Expiration-state regression test.
