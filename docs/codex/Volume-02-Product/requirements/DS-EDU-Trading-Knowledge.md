# DS-EDU — Trading Knowledge & Education

| Field | Value |
|---|---|
| Document ID | DS-EDU |
| Title | Trading Knowledge & Education |
| Version | 0.1.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Added in the DS-002-H05 repair pass to close a product-capability gap: DS-001 §19.2 identifies trading knowledge/education as product direction and explicitly delegates its detailed requirements and content provenance to later Codex volumes, but no prior DS-002 family covered it. This family records the scope boundary and provenance principle now, without prematurely committing the full Trading Knowledge Engine.

## Requirements

### DS-EDU-001 — Contextual Terminology Reference

**Priority:** Low | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Give users a way to look up unfamiliar terminology and concepts encountered in the product, per DS-001 §19.2's education intent, without committing a full curriculum system.

**Description:** DarkSage should provide contextual, on-demand definitions or explanations for domain terminology, indicators, and concepts referenced elsewhere in the product (e.g., a term used in a chart, alert, or Sage response).

**Dependencies:** DS-001 §19.2; DS-AI-003 (explainability, if Sage is the delivery mechanism)

**Acceptance Criteria:**
- A user encountering an unfamiliar term used by the product can reach a definition/explanation without leaving their current context.
- Definitions are evidence-based and consistent with the terminology mode active (DS-USR-003) where applicable.

**Edge Cases:**
- A term with no authored definition yet discloses that gap rather than presenting a fabricated explanation (consistent with DS-PRD-002/DS-PRD-009 if Sage is the delivery mechanism).

**Implementation Notes:** Content authorship/curation process and provenance tracking belong to a future Codex volume per DS-001 §19.2; this requirement only establishes that the capability and its evidence-quality obligations exist once built.

**Testing:** Contextual-lookup regression test for a sample term set.

### DS-EDU-002 — Trading Knowledge Engine

**Priority:** Low | **Release Classification:** Future / Exploratory | **Status:** Draft

**Purpose:** Record DS-001 §19.2's Trading Knowledge Engine direction as a non-binding future capability, matching DS-001's own framing ("may organize and support this product direction").

**Description:** DarkSage may, in a future release, provide a structured educational/knowledge system (curriculum, guided learning, deeper contextual education) beyond simple contextual definitions (DS-EDU-001). This capability is not committed to the current MVP or Planned scope.

**Dependencies:** DS-001 §19.2; DS-EDU-001

**Acceptance Criteria:** N/A at Future/Exploratory classification; acceptance criteria will be defined if and when this item is promoted to Planned or Committed/MVP, including its content-provenance and evidence-based-learning obligations per DS-001 §19.2 ("evidence-based learning rather than unquestionable doctrine").

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** Detailed requirements, validation rules, and content provenance are explicitly delegated to a future Codex volume per DS-001 §19.2 and are not authored here.

**Testing:** Not applicable until promoted.

**Future Enhancements:** Guided curricula; progress tracking; personalized learning paths; integration with Sage's explainability output (DS-AI-003) as a source of teachable moments.

### DS-EDU-003 — Contextual Learning and Mastery

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall provide contextual explanations tied to the user's current chart, signal, strategy, portfolio, or journal review; adapt depth to demonstrated knowledge; expose why a concept matters; and support learning progress without making the user permanently dependent on unexplained output.
