# DS-AI — Sage

| Field | Value |
|---|---|
| Document ID | DS-AI |
| Title | Sage |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Detailed Sage reasoning, memory, and evidence-governance behavior is delegated to DS-003; DS-AI defines the product-level requirement surface only.

**Release Classification note (added in the DS-002-A01 repair):** Sage itself is `ROADMAP.md` Phase 6 scope ("Local AI, Cloud Providers, and Sage"), not Phase 1. Every requirement below is therefore Planned as a *feature* — Sage does not exist yet in the current committed scope. This does not weaken any safety boundary: the moment Sage is built, it is unconditionally bound by the already-Committed cross-cutting requirements DS-PRD-001 (model independence), DS-PRD-002 (evidence provenance), DS-PRD-003 (presentation independence), DS-PRD-004 (deterministic financial truth), DS-PRD-005 (user decision authority), DS-PRD-006 (Risk Engine authority), DS-PRD-007 (no autonomous trading), DS-PRD-008 (data state visibility), DS-PRD-009 (uncertainty communication), and DS-PRD-011 (AI output validation) — these govern Sage whenever it exists, regardless of this family's own Planned classification.

## Requirements

### DS-AI-001 — Conversational Interaction

**Priority:** Critical | **Release Classification:** Planned (Phase 6, `ROADMAP.md`) | **Status:** Draft

**Purpose:** Provide the primary interface through which users engage Sage's reasoning and explanation capability.

**Description:** DarkSage shall provide a natural-language conversational interface to Sage, available regardless of which workspace widgets are currently visible, per DS-PRD-003.

**Dependencies:** DS-PRD-003; DS-PRD-005

**Acceptance Criteria:**
- Users can ask Sage questions and receive responses grounded in enabled evidence (DS-AI-002).
- The conversational surface remains reachable independent of workspace layout/widget visibility.
- Sage's responses distinguish recommendation language from confirmed/executed-action language (DS-PRD-005).

**Edge Cases:**
- An ambiguous or out-of-scope user query results in Sage disclosing the ambiguity or limitation rather than fabricating a confident answer.

**Implementation Notes:** Conversation UI is a DS-007 concern; reasoning/memory behavior is a DS-003 concern.

**Testing:** Conversational regression test set including ambiguous/out-of-scope queries.

### DS-AI-002 — Evidence Access Independent of Presentation

**Priority:** Critical | **Release Classification:** Planned (Phase 6, `ROADMAP.md`) | **Status:** Draft

**Purpose:** Guarantee Sage's evidence is governed by enabled capability, not by what happens to be visible on screen, per ADR-004.

**Description:** Sage shall use enabled system intelligence and evidence when relevant to a query, regardless of whether the corresponding widgets are visible in the current workspace.

**Dependencies:** DS-PRD-003; ADR-004; DS-MKT; DS-RSK; DS-PRT

**Acceptance Criteria:**
- Sage can cite evidence from any enabled data source/capability even when its corresponding widget is hidden or absent from the active workspace.
- Disabling a capability (not merely hiding its widget) does remove it from Sage's available evidence — the boundary is capability state, not presentation state.

**Edge Cases:**
- A capability disabled mid-conversation is reflected in Sage's subsequent responses without requiring a new conversation.

**Implementation Notes:** DS-003/DS-004 concern for evidence-access architecture.

**Testing:** Widget-hidden and capability-disabled evidence-availability regression tests (contrasting outcomes).

### DS-AI-003 — Explainability

**Priority:** Critical | **Release Classification:** Planned (Phase 6, `ROADMAP.md`) | **Status:** Draft

**Purpose:** Ensure Sage's material conclusions can be understood, not merely accepted, per DS-001 §15.

**Description:** For a material conclusion or recommendation, Sage shall be able to state the supporting evidence, its currency/strength, material uncertainty, material risks, key assumptions, and what would invalidate the conclusion.

**Dependencies:** DS-001 §15; DS-PRD-002; DS-PRD-009

**Acceptance Criteria:**
- On request, Sage provides an explanation covering the DS-001 §15 explainability questions applicable to the conclusion at hand.
- An explanation discloses limitations/conflicts rather than concealing them behind polished language (DS-001 §15).
- Where evidence is insufficient, Sage states uncertainty or abstains rather than fabricating a confident conclusion.

**Edge Cases:**
- A conclusion whose evidence has partially expired discloses which portion is current vs. stale (DS-PRD-008).

**Implementation Notes:** DS-003 concern for explanation-generation architecture.

**Testing:** Explanation-completeness test against the DS-001 §15 question set for a sample of material conclusion types.

### DS-AI-004 — Confidence and Uncertainty Communication

**Priority:** High | **Release Classification:** Planned (Phase 6, `ROADMAP.md`) | **Status:** Draft

**Purpose:** Apply DS-PRD-009's uncertainty mandate concretely to Sage's own output.

**Description:** Sage shall communicate confidence/uncertainty for probabilistic or inferential statements using a consistent, defined vocabulary or scale, distinct from deterministic factual statements.

**Dependencies:** DS-PRD-009; DS-AI-003

**Acceptance Criteria:**
- Sage's probabilistic/inferential statements are visually and textually distinguishable from statements of observed fact or deterministic calculation.
- The confidence vocabulary/scale used is consistent across all Sage output surfaces.

**Edge Cases:**
- A high-confidence inference is still labeled as an inference, never upgraded to fact-level presentation (DS-PRD-009).

**Implementation Notes:** Vocabulary/scale definition is a DS-003 deliverable; DS-AI requires its consistent application.

**Testing:** Output-labeling audit across sampled Sage responses.

### DS-AI-005 — Model/Provider Abstraction

**Priority:** High | **Release Classification:** Planned (Phase 6, `ROADMAP.md`) | **Status:** Draft

**Purpose:** Apply DS-PRD-001's model-independence mandate at the Sage implementation-requirement level, including local vs. external provider handling.

**Description:** Sage's product-facing behavior shall be defined independent of any specific AI model or provider implementation, including whether that provider is local or external, per DS-PRD-001.

**Dependencies:** DS-PRD-001; DS-AI-001

**Acceptance Criteria:**
- No Committed/MVP Sage requirement's acceptance criteria depend on a named vendor's specific behavior.
- A local-model and an external-model provider, if both implemented, satisfy the same product-facing requirements without user-visible functional inconsistency beyond disclosed capability differences.

**Edge Cases:**
- A capability available only from one provider type (local or external) at a given time discloses that limitation rather than silently degrading without explanation.

**Implementation Notes:** Provider-abstraction architecture is a DS-004 concern.

**Testing:** Cross-provider behavioral parity test where more than one provider is implemented.

### DS-AI-006 — AI Failure and Degradation Behavior

**Priority:** High | **Release Classification:** Planned (Phase 6, `ROADMAP.md`) | **Status:** Draft

**Purpose:** Prevent an AI outage or degradation from silently misleading the user or blocking deterministic functionality.

**Description:** When Sage or an underlying AI provider is unavailable or degraded, DarkSage shall disclose the degraded state to the user and shall continue to provide deterministic functionality (DS-PRD-004) unaffected by the AI outage.

**Dependencies:** DS-PRD-004; DS-PRD-001; DS-OPS

**Acceptance Criteria:**
- An AI provider outage is surfaced to the user in the conversational surface rather than presented as a silent empty/broken response.
- Deterministic features (calculations, charts, deterministic scan filtering) remain fully functional during an AI outage.
- The outage/degradation event is logged per DS-OPS.

**Edge Cases:**
- A partial degradation (e.g., elevated latency, reduced model capability) is disclosed proportionately rather than only a full outage being disclosed.

**Implementation Notes:** DS-004/DS-008 concern for failover/circuit-breaker architecture.

**Testing:** Simulated-outage test verifying disclosure and continued deterministic functionality.

### DS-AI-007 — Sage Cannot Bypass the Risk Engine

**Priority:** Critical | **Release Classification:** Planned (Phase 6, `ROADMAP.md`) | **Status:** Draft

**Purpose:** Restate ADR-002/DS-PRD-006's boundary at the Sage requirement level for direct traceability.

**Description:** Sage shall not issue, narrate, or facilitate any action that bypasses or silently overrides a Risk Engine (Guardian) determination.

**Dependencies:** ADR-002; DS-PRD-006; DS-RSK

**Acceptance Criteria:** See DS-PRD-006 acceptance criteria; this requirement exists for direct DS-AI-family traceability and does not restate additional criteria.

**Edge Cases:** See DS-PRD-006.

**Implementation Notes:** Enforcement architecture belongs to DS-004/DS-008; DS-AI-007 exists to ensure the Sage requirement family cannot be read in isolation from this boundary.

**Testing:** See DS-PRD-006 adversarial test.
