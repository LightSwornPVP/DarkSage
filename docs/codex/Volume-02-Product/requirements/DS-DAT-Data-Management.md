# DS-DAT — Data Management

| Field | Value |
|---|---|
| Document ID | DS-DAT |
| Title | Data Management |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5.

## Requirements

### DS-DAT-001 — Local Data Storage

**Priority:** Critical | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Implement DS-001 §14's local-first preference as a concrete storage obligation.

**Description:** DarkSage shall store user-generated data (preferences, workspaces, watchlists, transactions, strategies, scan/backtest history) locally by default, consistent with DS-001 §14's local-first-where-practical preference.

**Dependencies:** DS-001 §14; DS-SEC

**Acceptance Criteria:**
- Core Committed/MVP data categories are stored locally without requiring an external/cloud service as a precondition.
- Any future optional cloud sync/backup remains explicitly opt-in and does not silently duplicate data externally.

**Edge Cases:**
- Local storage corruption/unavailability is disclosed per DS-OPS rather than silently losing data without notice.

**Implementation Notes:** Storage engine/schema is a DS-004/DS-005 concern.

**Testing:** Offline functional test confirming core data categories are locally readable/writable without network access.

### DS-DAT-002 — Data Import and Export

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Let users bring in existing records and take their data with them, avoiding lock-in.

**Description:** DarkSage shall support import and export of user data (at minimum transactions and watchlists) in a documented, structured format.

**Dependencies:** DS-PRT-002; DS-MKT-007; DS-SEC

**Acceptance Criteria:**
- Exported data can be re-imported into the same or another DarkSage instance and reproduces equivalent records.
- Import validates records before commit and reports per-record failures rather than failing an entire batch silently (see DS-PRT-002).

**Edge Cases:**
- An export containing sensitive data (e.g., account identifiers) is disclosed to the user before the export completes, consistent with DS-SEC privacy requirements.

**Implementation Notes:** Format specification is a DS-005/DS-006 concern.

**Testing:** Round-trip export/import regression test; malformed-import rejection test.

### DS-DAT-003 — Symbol and Security Identity

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Governing Source:** `ROADMAP.md` Phase 1 ("Core models," "Candle model," "Quote model"); `ARCHITECTURE.md` §6 (Shared Models) — a stable identity concept is baseline necessity for these Phase 1 models.

**Purpose:** Give Phase-1 market data models (Candle, Quote, Signal) a single, unambiguous reference for "which security is this," distinct from a mutable display ticker.

**Description:** DarkSage shall maintain a canonical internal identity for each tracked security, distinct from its display ticker/symbol, used by Candle, Quote, and Signal records (Phase 1 scope).

**Dependencies:** DS-MKT-001 (Committed); `ARCHITECTURE.md` §6

**Acceptance Criteria:**
- Every Candle, Quote, and Signal record resolves through the canonical internal identity, not the display ticker alone.
- A ticker/symbol change updates the display label without breaking existing Candle/Quote/Signal references to the underlying canonical identity.

**Edge Cases:**
- Two distinct securities that briefly share a ticker (e.g., after a delisting and reuse) resolve to distinct canonical identities, not merged.

**Implementation Notes:** DS-004/DS-005 concern for the identity schema.

**Testing:** Ticker-change continuity regression test (Candle/Quote/Signal scope); ticker-reuse disambiguation test.

**Future Enhancements (Planned, not part of this requirement's Committed/MVP scope):** Once DS-MKT-006 (corporate actions), DS-MKT-007 (watchlists), and DS-PRT-001 (positions) are built, they extend this same canonical identity to their own references rather than introducing a parallel identity scheme — that extension is governed by DS-MKT-006/007 and DS-PRT-001's own (Planned) requirements, not by this Committed core.

### DS-DAT-004 — Data Retention and Deletion

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Give users control over how long their data is kept and the ability to remove it.

**Description:** DarkSage should allow users to configure retention limits for non-authoritative history (e.g., scan history, DS-SCN-005) and to delete their locally stored data on request.

**Dependencies:** DS-DAT-001; DS-SCN-005; DS-SEC

**Acceptance Criteria:**
- A user-initiated deletion request removes the targeted local data category without requiring external-service coordination for locally stored data.
- Authoritative records (e.g., confirmed transactions, DS-PRT-002) are not silently pruned by a retention policy without explicit user action.

**Edge Cases:**
- A deletion request affecting data referenced elsewhere (e.g., a watchlist referencing a deleted scan's symbols) resolves the reference gracefully rather than corrupting the referencing record.

**Implementation Notes:** DS-004/DS-005/DS-008 concern.

**Testing:** Retention-limit enforcement test; deletion-request completeness test.
