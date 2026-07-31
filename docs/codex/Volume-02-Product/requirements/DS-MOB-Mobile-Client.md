# DS-MOB — Mobile Client

| Field | Value |
|---|---|
| Document ID | DS-MOB |
| Title | Mobile Client |
| Version | 0.1.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5. Added in the DS-002-A03 repair pass. Product-level requirements for the mobile client; the architectural contract lives in DS-004 (DS-ARC-003).

## Requirements

### DS-MOB-001 — Mobile Client Scope

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `ARCHITECTURE.md` §4, §29; `PROJECT_SPEC.md` §29; `ROADMAP.md` Phase 9

**Purpose:** Fix what the mobile client is for, without committing it to current scope.

**Description:** DarkSage should provide a mobile client (iPhone-first) covering dashboard, signals, watchlists, charts, portfolio monitoring, Sage chat, Auto-Trader status, emergency stop, trade approvals, and push notifications.

**Dependencies:** DS-ARC-003; DS-ARC-001

**Acceptance Criteria:** Deferred to Phase 9 authoring; not yet testable at Planned classification.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `ARCHITECTURE.md` §4/§29 is the authoritative scope reference.

**Testing:** Not yet applicable — Phase 9.

### DS-MOB-002 — Mobile Cannot Run Core Trading Logic

**Priority:** Critical | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `AGENTS.md` "Mobile/Backend Rule"; `ARCHITECTURE.md` §4; DS-ARC-001

**Purpose:** Fix this boundary as Committed now, before mobile exists, so it cannot be quietly relaxed once mobile development begins under schedule pressure — the same reasoning as DS-EXE-007's live-trading gate.

**Description:** The mobile client shall not independently run the full scanner, backtester, or execution engine, and shall not store authoritative trading state; whenever a mobile client is built, it is a client of the backend API per DS-ARC-001, with the backend as the sole source of truth.

**Dependencies:** DS-ARC-001; DS-MOB-001

**Acceptance Criteria:**
- No future mobile-client design proposal may include local execution of core trading logic without a new ADR.
- Mobile can stop paper/live Auto-Trading even if it was enabled from desktop (backend-authoritative state), once Auto-Trader exists.

**Edge Cases:** None beyond DS-ARC-001's existing edge cases.

**Implementation Notes:** This requirement exists at the product level so it is checked independent of whether DS-ARC-003 itself has been promoted past Planned.

**Testing:** Requirements review; cross-client state-consistency test once mobile and Auto-Trader both exist (Phase 9).

### DS-MOB-003 — Strong Authentication for High-Risk Mobile Actions

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Governing Source:** `SECURITY_RULES.md` "Strong Authentication," "Desktop and Mobile Security"; `ROADMAP.md` Phase 9

**Purpose:** Ensure mobile's convenience (stopping Auto-Trade from a phone) doesn't become a weaker security surface than desktop.

**Description:** DarkSage should require strong authentication for high-risk mobile actions (emergency flatten, trade approvals, live-trading changes) and should use secure platform storage (e.g., iOS Keychain) rather than storing broker secrets directly on the device.

**Dependencies:** DS-MOB-001; DS-SEC-001

**Acceptance Criteria:** Deferred to Phase 9 authoring; the secure-storage and strong-authentication obligations are fixed now per the Governing Source.

**Edge Cases:** None recorded at this classification level.

**Implementation Notes:** `SECURITY_RULES.md` is authoritative.

**Testing:** Not yet applicable — Phase 9.
