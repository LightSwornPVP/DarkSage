# DS-EXE — Execution, Auto-Trader & Broker

| Field | Value |
|---|---|
| Document ID | DS-EXE |
| Title | Execution, Auto-Trader & Broker |
| Version | 0.1.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Added in the DS-002-A03 repair pass. Product-level requirements for the canonical `TradeValidationPipeline` and Auto-Trader/Broker capability; the architectural contract lives in DS-004 (DS-ARC-011/012). This family states product-level obligations; it does not authorize live trading (DS-PRD-007 remains controlling).

## Requirements

### DS-EXE-001 — TradeValidationPipeline Is the Only Path to an Order

**Priority:** Critical | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** ADR-002; DS-PRD-006, DS-PRD-007; `ARCHITECTURE.md` §14; `TRADING_RULES.md` Core Rules #2–#3; DS-ARC-011 (Planned, Phase 7 implementation)

**Purpose:** State, as a Committed product-level requirement (not merely an architecture note), that no path to broker execution may exist outside the canonical pipeline — this governs the product even before the pipeline is implemented, preventing any interim shortcut from ever being built.

**Description:** DarkSage shall never provide, now or in any future release, a path from a Trade Proposal to a Broker Adapter that does not pass through every stage of the canonical `TradeValidationPipeline` (`ARCHITECTURE.md` §14) in full and in order. This obligation is unconditional and does not depend on which phase implements the pipeline.

**Dependencies:** ADR-002; DS-PRD-006; DS-PRD-007; DS-ARC-011

**Acceptance Criteria:**
- No Committed/MVP or Planned requirement in this Codex authorizes a trade-execution path that bypasses any pipeline stage.
- Introducing any alternate execution path requires a new ADR, not an amendment to this requirement's scope.

**Edge Cases:** None beyond ADR-002's existing scope.

**Implementation Notes:** DS-ARC-011 (DS-004) implements the pipeline itself, Planned for Phase 7; this requirement is the product-level governance constraint that exists regardless of implementation timing.

**Testing:** Requirements review — reject any proposed requirement or design that would create an alternate execution path.

### DS-EXE-002 — Trade Proposal Representation

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §14; `ROADMAP.md` Phase 7; `PROJECT_SPEC.md` §2.3

**Purpose:** Give the AI/Strategy Engine's advisory output a structured shape before it can be validated.

**Description:** DarkSage should represent a Trade Proposal produced by the AI/Strategy Engine as a structured object (signal reference, strategy reference, proposed size/direction) that is advisory-only until validated by the full pipeline.

**Dependencies:** DS-EXE-001; DS-SIG-001; DS-DB-007 (DS-005)

**Acceptance Criteria:** Deferred to Phase 7 authoring; not yet testable at Planned classification beyond the unconditional boundary in DS-EXE-001.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `ARCHITECTURE.md` §14/PROJECT_SPEC §2.3 are authoritative for the proposal's relationship to the pipeline.

**Testing:** Not yet applicable — Phase 7.

### DS-EXE-003 — Auto-Trader State Model

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §15; `ROADMAP.md` Phase 7

**Purpose:** Give the Auto-Trader a small, well-defined state machine that every client observes identically.

**Description:** DarkSage should represent Auto-Trader state as one of: disabled, enabled, paused, emergency_stop, held authoritatively in the backend (DS-ARC-001) and observed identically by desktop and any future mobile client.

**Dependencies:** DS-ARC-001; DS-EXE-004

**Acceptance Criteria:** Deferred to Phase 7 authoring.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `ARCHITECTURE.md` §15 is authoritative.

**Testing:** Not yet applicable — Phase 7.

### DS-EXE-004 — Emergency Stop

**Priority:** Critical | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §16; `TRADING_RULES.md`/`SECURITY_RULES.md` "Emergency Stop"; `ROADMAP.md` Phase 7

**Purpose:** Guarantee a fast, reliable way to halt new automated activity once the Auto-Trader exists, without waiting for a slower design process once execution is live.

**Description:** DarkSage should provide an Emergency Stop control that blocks all new orders immediately, cancels pending entry orders, and continues monitoring existing positions; any authorized DarkSage client should be able to trigger it, and it must be easier to trigger than to enable live trading.

**Dependencies:** DS-EXE-003; `SECURITY_RULES.md`

**Acceptance Criteria:** Deferred to Phase 7 authoring; the requirement's shape (block/cancel/continue-monitoring, cross-client trigger) is fixed now per the Governing Source.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `TRADING_RULES.md`/`SECURITY_RULES.md` are authoritative for exact behavior.

**Testing:** Not yet applicable — Phase 7 exit criterion ("Emergency Stop passes tests").

### DS-EXE-005 — Emergency Flatten

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §16; `SECURITY_RULES.md` "Emergency Controls"; `ROADMAP.md` Phase 7

**Purpose:** Provide a more forceful de-risking control than Emergency Stop, gated appropriately given its higher blast radius.

**Description:** DarkSage should provide an Emergency Flatten control (block new orders, cancel open orders, close active positions per emergency rules) that requires strong authentication in live mode.

**Dependencies:** DS-EXE-004

**Acceptance Criteria:** Deferred to Phase 7/13 authoring; the strong-authentication-in-live-mode requirement is fixed now per the Governing Source.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `SECURITY_RULES.md` is authoritative for the authentication requirement.

**Testing:** Not yet applicable — Phase 7 (paper) / Phase 13 (live).

### DS-EXE-006 — Broker Adapter Abstraction

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §14; `ROADMAP.md` Phase 7

**Purpose:** Prevent broker vendor lock-in, mirroring DS-ARC-006's market-data provider abstraction.

**Description:** DarkSage should implement broker connectivity through a common Broker Adapter interface, with PaperBroker as the initial implementation; live broker adapters are a later, separately-gated addition.

**Dependencies:** DS-EXE-001; DS-ARC-001

**Acceptance Criteria:** Deferred to Phase 7 authoring.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `ARCHITECTURE.md` §14 is authoritative.

**Testing:** Not yet applicable — Phase 7.

### DS-EXE-007 — Live Trading Gate

**Priority:** Critical | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** DS-PRD-007; `TRADING_RULES.md` "Live Trading Requirements"; `SECURITY_RULES.md` "Live Trading"; `ROADMAP.md` Phase 13

**Purpose:** Fix the prerequisite gate for live trading as a Committed governance requirement now, so it cannot be silently weakened later when the temptation to ship live trading faster exists.

**Description:** DarkSage shall not enable live trading until, at minimum: paper performance is acceptable per defined strategy-promotion requirements, an independent security review has passed, broker reconciliation has passed, the kill switch (Emergency Stop/Flatten) has passed testing, data-health checks have passed, duplicate-order prevention has passed, monitoring is active, and the user has explicitly and separately unlocked live trading. No development agent or AI process may enable live trading.

**Dependencies:** DS-PRD-007; DS-EXE-004, DS-EXE-005, DS-EXE-006 (Planned; must exist before this gate can be satisfied)

**Acceptance Criteria:**
- No code path enables live trading without every listed prerequisite having passed.
- No AI agent, background process, or automated tooling can flip the live-trading flag; only an explicit, authenticated user action can.

**Edge Cases:** None beyond the listed prerequisites.

**Implementation Notes:** `TRADING_RULES.md`/`SECURITY_RULES.md` are authoritative for the complete prerequisite list.

**Testing:** Requirements/governance review — this gate is Committed now specifically so it can be checked at any future point regardless of implementation phase.
