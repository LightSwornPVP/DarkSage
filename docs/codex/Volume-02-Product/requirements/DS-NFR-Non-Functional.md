# DS-NFR — Non-Functional Requirements

| Field | Value |
|---|---|
| Document ID | DS-NFR |
| Title | Non-Functional |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Per DS-002 §5, vague terms ("fast," "smart," "reliable") are avoided unless bound to a measurable acceptance criterion below.

## Requirements

### DS-NFR-001 — Startup Performance

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Bound DS-PRD-010's startup obligation with a measurable target.

**Description:** DarkSage shall reach an interactive workspace state (per DS-PRD-010) within a defined startup time budget on reference hardware, for both cold-start and warm-start cases.

**Governing Threshold (controlled product default, added in the DS-002-A04 repair):** Reference hardware: quad-core CPU (2018 or later), 8 GB RAM, SSD storage, Windows 10/11 or equivalent. Cold start (no OS-level file cache): interactive workspace state within **10 seconds**. Warm start (OS cache warm): within **3 seconds**. These are controlled product defaults, not architecture-chosen values; DS-004 may define *how* they are measured and achieved, but does not choose the product-acceptance number itself. Revising either value is a product decision (update this line + Revision History), not a silent DS-004 implementation choice.

**Dependencies:** DS-PRD-010

**Acceptance Criteria:**
- Cold-start (no OS-level cache) reaches interactive state within 10 seconds on the reference hardware defined above.
- Warm-start reaches interactive state within 3 seconds on the reference hardware defined above.
- Startup time is measured and regression-tracked, not assessed subjectively.

**Edge Cases:**
- A startup exceeding budget due to a slow/unavailable dependency (DS-PRD-010) still communicates progress rather than appearing frozen.

**Implementation Notes:** DS-004 defines *how* startup time is measured and optimized (profiling methodology, instrumentation); the 10s/3s budgets themselves are the product acceptance target set above and are not DS-004's to choose.

**Testing:** Automated startup-time regression benchmark on defined reference hardware/profile.

### DS-NFR-002 — Interaction Responsiveness

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Bound workspace interaction latency with a measurable target rather than a subjective "fast" claim.

**Description:** DarkSage shall complete common interactive operations (widget add/remove/resize, layout drag, watchlist edit) within a documented maximum latency budget, measured under defined test conditions.

**Dependencies:** DS-WKS-001; DS-WKS-002; DS-MKT-007

**Acceptance Criteria:**
- Each Committed/MVP interactive operation has a documented maximum latency budget (defined in DS-004) that is regression-tracked.
- A budget breach is flagged by automated performance testing, not left to subjective user report alone.

**Edge Cases:**
- An operation whose latency depends on external data (e.g., a live quote fetch) separates local UI responsiveness from external data latency in its measurement.

**Implementation Notes:** Numeric budgets belong to DS-004.

**Testing:** Automated latency regression benchmark per interaction type.

### DS-NFR-003 — Reliability and Crash Resilience

**Priority:** Critical | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Bound "reliable" with a measurable, testable definition.

**Description:** DarkSage shall recover from an unexpected application termination without loss of previously saved data (workspaces, transactions, strategies, preferences), and shall log the termination event per DS-OPS.

**Dependencies:** DS-DAT-001; DS-OPS

**Acceptance Criteria:**
- A simulated crash/forced termination followed by relaunch restores all data saved prior to the crash.
- Data not yet saved at the time of a crash is clearly distinguished from saved data on relaunch (no silent conflation).
- The crash event is logged with sufficient detail for diagnosis (DS-OPS), without exposing secrets (DS-SEC-001).

**Edge Cases:**
- A crash during an in-progress write (e.g., mid-save) does not corrupt the previously committed saved state.

**Implementation Notes:** DS-004/DS-005 concern for durable-write architecture.

**Testing:** Forced-termination-and-relaunch regression test; mid-write interruption test.

### DS-NFR-004 — Accessibility

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Ensure the product is usable by users relying on assistive technology or keyboard-only interaction.

**Description:** DarkSage shall support keyboard-only operation of Committed/MVP workflows and shall conform to a documented accessibility standard (e.g., WCAG 2.2 Level AA) for applicable desktop UI patterns, as detailed in DS-007.

**Dependencies:** DS-WKS-002; DS-007

**Acceptance Criteria:**
- Every Committed/MVP workflow (including workspace layout editing, per DS-WKS-002) is completable without a pointing device.
- Text contrast and status indication do not rely on color alone (consistent with `docs/standards/BRAND_GUIDE.md`).

**Edge Cases:**
- A chart or visualization conveying status by color also conveys it via text/label.

**Implementation Notes:** Full accessibility specification belongs to DS-007; DS-NFR-004 establishes the product-level obligation and standard reference.

**Testing:** Keyboard-only workflow completion test; automated accessibility-conformance scan against the documented standard.

### DS-NFR-005 — Maintainability and Extensibility

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Bound "maintainable"/"extensible" with a testable structural expectation rather than a vague aspiration.

**Description:** DarkSage shall structure Committed/MVP capability (data providers, AI providers, widgets) behind documented extension points (per DS-PRD-001, DS-INT-001) such that a new provider or widget can be added without modifying unrelated requirement families' behavior.

**Dependencies:** DS-PRD-001; DS-INT-001; DS-WKS-001

**Acceptance Criteria:**
- Adding a new data provider, AI provider, or widget type is achievable through the documented extension point without editing other families' requirement-level behavior.
- Extension points are documented in DS-004/DS-010.

**Edge Cases:** None beyond the extension-point contract itself.

**Implementation Notes:** DS-004/DS-010 concern for the concrete extension mechanism.

**Testing:** Extension-point regression test: add a fixture provider/widget and confirm no unrelated family behavior changes.

### DS-NFR-006 — Testing Expectations

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Establish a baseline testing expectation for Committed/MVP requirements at the product-requirements level, without prescribing DS-009's detailed test procedure.

**Description:** Every Committed/MVP requirement across all DS-002 family documents shall have at least one associated automated or documented manual test, as stated in that requirement's Testing field.

**Dependencies:** DS-009 (future volume)

**Acceptance Criteria:**
- No Committed/MVP requirement in this document set has an empty or missing Testing field.
- Deterministic calculation requirements (DS-PRD-004 and its dependents) have automated regression tests, not manual-only verification, once implemented.

**Edge Cases:** None beyond the completeness check itself.

**Implementation Notes:** Detailed test strategy, coverage targets, and tooling belong to DS-009.

**Testing:** Requirements-completeness audit confirming every Committed/MVP requirement has a non-empty Testing field (performed as part of DS-002 self-verification; see HANDOFF.md for this task).
