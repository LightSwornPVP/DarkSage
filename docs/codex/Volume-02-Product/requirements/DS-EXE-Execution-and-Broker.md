# DS-EXE — Execution, Auto-Trader & Broker

| Field | Value |
|---|---|
| Document ID | DS-EXE |
| Title | Execution, Auto-Trader & Broker |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-25 |

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

### DS-EXE-008 — Automation Mode Model

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** DS-EXE-001, DS-EXE-003, DS-EXE-004, DS-EXE-005, DS-EXE-007; ADR-002; DS-PRD-007; `TRADING_RULES.md`; `ROADMAP.md` Phase 7/13. Added as a narrow controlled amendment recording the Founder-approved automation direction; does not alter any prerequisite already fixed by DS-EXE-007.

**Purpose:** Give the user-facing automation-authority level (how much unattended discretion the system currently holds) a single, named, five-value model, distinct from — and layered on top of — DS-EXE-003's lower-level Auto-Trader process state (disabled/enabled/paused/emergency_stop). This closes a naming gap the Founder Vision Alignment review flagged: the risk of conflating Sage's permanent advisory-only boundary (ADR-002 — Sage may never place an order) with the Auto-Trader's separate, phased path toward live execution authority.

**Description:** DarkSage shall represent the current automation mode as exactly one of the following five values, authoritative in the backend (DS-ARC-001) and observed identically by every client:

1. **Advisory Only** — Sage/the Signal system may propose and explain; no order of any kind is placed automatically; every trade requires full manual entry by the user. This is the mode in which ADR-002's Sage-never-executes boundary is the *only* automation boundary in effect.
2. **Confirmation Required** — the system may prepare a fully validated Trade Proposal (having passed every `TradeValidationPipeline` stage per DS-EXE-001) but must not submit it to the Broker Adapter until the user explicitly confirms that specific trade.
3. **Full-Auto Paper** — the system may submit validated Trade Proposals to the PaperBroker without per-trade confirmation, for approved strategies only, unattended, subject to realistic simulated fees/spreads/slippage/partial-fills/rejections/failures (DS-EXE-006), with complete audit history and versioned strategy behavior. Sage may analyze results and propose strategy revisions but may never silently modify an active strategy's live behavior — any change requires the same promotion/versioning path as a new strategy version.
4. **Restricted Full-Auto Live** — a real, future-supported mode requiring separate live authorization on top of DS-EXE-007's Live Trading Gate; no per-trade approval once explicitly authorized, approved strategies only, operating inside a precommitted deterministic risk envelope (position/size/loss limits fixed while the user is calm, not adjustable mid-session), with mandatory lockouts, mobile monitoring and pause capability (DS-MOB-002), and Emergency Stop/Emergency Flatten remaining distinct controls (DS-EXE-004/DS-EXE-005) that Sage cannot override. This mode is **Planned/Future-gated, not Committed/MVP** — it does not become available merely because Full-Auto Paper exists; DS-EXE-007's full prerequisite list applies in addition to this requirement.
5. **Paused / Emergency Stopped** — maps directly onto DS-EXE-003's `paused`/`emergency_stop` states; available as an immediate override from any of modes 1–4.

**Precommitment rules (apply to modes 3–4):** the user selects strategy and risk boundaries while calm, before automation begins; pausing or reducing risk may take effect immediately; any *increase* in risk (position size, loss limit, symbol universe, or a mode transition toward more autonomy, e.g. Confirmation Required → Full-Auto Paper, or Full-Auto Paper → Restricted Full-Auto Live) requires stronger confirmation than a decrease, and may require reauthentication, a cooling-off interval, or next-session activation rather than taking effect immediately. Any strategy behavior change requires versioning and revalidation through the existing promotion pipeline (DS-STR/DS-BKT/DS-PERF-004) before it can run under Full-Auto Paper or Restricted Full-Auto Live.

**Dependencies:** DS-EXE-001, DS-EXE-003, DS-EXE-004, DS-EXE-005, DS-EXE-006, DS-EXE-007; DS-MOB-002; ADR-002

**Acceptance Criteria:**
- Exactly one of the five named modes is authoritative at any time, held in the backend, never independently derived by a client.
- No mode transition toward greater automation authority (e.g. into Full-Auto Paper or Restricted Full-Auto Live, or any risk-envelope increase within them) takes effect without the confirmation strength defined above; transitions toward less authority (Pause/Emergency Stop, or a risk decrease) may take effect immediately.
- Restricted Full-Auto Live remains gated by every DS-EXE-007 prerequisite in addition to this requirement; nothing in this requirement authorizes live trading on its own.
- Sage may never place an order directly in any mode (ADR-002 is unconditional); "automation" in modes 3–4 refers exclusively to the deterministic `TradeValidationPipeline` → Broker Adapter path, never to Sage bypassing that pipeline.

**Edge Cases:** A mode-transition request arriving while an Emergency Stop/Flatten is in effect must be rejected until the emergency state is explicitly cleared by the user.

**Implementation Notes:** Deferred to Phase 7 (modes 1–3) / Phase 13 (mode 4) authoring; this requirement fixes the model and naming now so client UI and audit logging can be designed against a stable vocabulary.

**Testing:** Not yet applicable — Phase 7/13; requirements/governance review confirms no unrestricted live automation classification has been silently elevated to Committed/MVP by this entry.
