# DS-JRN — Journal & Review Intelligence

| Field | Value |
|---|---|
| Document ID | DS-JRN |
| Title | Journal & Review Intelligence |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md).

## Requirements

### DS-JRN-001 — Structured Trade Journal
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall allow a user to preserve the original thesis, strategy/version, planned entry/stop/targets/size, chart state, evidence, contradictions, emotional context, actual execution, outcome, rule adherence, mistakes, and lessons for each reviewed trade or decision not to trade.

### DS-JRN-002 — Immutable Original Plan and Attributable Amendments
**Priority:** Critical | **Release Classification:** Planned | **Status:** Draft

**Description:** The original plan shall remain recoverable; later edits, annotations, and Sage observations shall be timestamped and attributable so hindsight cannot silently replace the initial reasoning.

### DS-JRN-003 — Daily Review
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall support a daily review of performance, plan adherence, risk, missed or avoided trades, recurring mistakes, meaningful market changes, and the next-session watchlist.

### DS-JRN-004 — Weekly Review and Pattern Discovery
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall support weekly aggregation of strategy performance, discipline, behavioral patterns, exposure, lessons, and improvement actions without presenting correlation as proven causation.

### DS-JRN-005 — Sage Coaching Boundary
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** Sage may analyze journal records, ask reflective questions, identify recurring patterns, and propose learning actions; it shall distinguish observation from inference and shall not diagnose medical or psychological conditions.

### DS-JRN-006 — Safe Progression
**Priority:** Medium | **Release Classification:** Future / Exploratory | **Status:** Draft

**Description:** Optional progression may reward education, preparation, journal completion, risk discipline, strategy validation, and process consistency; it shall not reward raw trade frequency, excessive leverage, or profit without risk/process context.

### DS-JRN-007 — Journal Retention and Deletion

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Give users explicit, user-controlled retention and deletion authority over their own journal content, closing a gap identified by independent audit: DS-JRN's privacy-relevant content (emotional context, mistake classification, behavioral notes) had no specific retention/deletion contract despite DS-001 §14's data-minimization principle applying to it.

**Description:** DarkSage shall allow a user to configure a retention period for JournalEntry (DS-DB-032) content and to request deletion of a specific entry or all journal content, including its user-entered emotional/private context and any attached chart-snapshot/attachment references. Deletion propagates to attachments and to derived DailyReview/WeeklyReview (DS-DB-033) content that would otherwise reproduce the deleted entry's private text; Sage-generated review drafts referencing a deleted entry are deleted or redacted consistently with DS-DAT-004's deletion-request completeness principle. Deletion never removes the immutable execution/audit record a journal entry may reference (e.g., the underlying Transaction, DS-DB-025, or AuditLogEntry, DS-DB-020) — personal journal narrative and immutable trade/audit records are distinct data classes with independent retention rules; only the personal narrative is user-deletable. Where a legal/audit exception requires retaining a consequential trade record, that record's factual fields (not the user's private commentary) may be retained per documented policy, disclosed to the user at deletion time. A user may export their journal content before deleting it, where export (DS-DAT-002) is supported. Deletion status (pending/completed/failed) is reported to the user; a failure discloses the reason rather than silently appearing to succeed. Deletion-related logging (DS-OPS-001) never reproduces the deleted content itself — a log entry references the deleted record's identifier and timestamp only, never its private text.

**Dependencies:** DS-DAT-004 (Data Retention and Deletion); DS-JRN-001, DS-JRN-002, DS-JRN-003, DS-JRN-004; DS-SEC-001, DS-SEC-002; DS-DB-032, DS-DB-033 (DS-005)

**Acceptance Criteria:**
- A user-initiated deletion request removes the targeted JournalEntry's private/emotional content and its attachment references without requiring external-service coordination for locally stored data.
- Deletion propagates to DailyReview/WeeklyReview content and Sage-generated review drafts that would otherwise reproduce the deleted entry's private text; deterministic performance figures (DS-PERF/DS-PRT references) in those reviews are unaffected since they are not the user's private content.
- A JournalEntry's link to an immutable Transaction (DS-DB-025) or AuditLogEntry (DS-DB-020) is never itself deleted by this requirement; only the personal journal narrative is deletable, and the distinction is disclosed to the user before deletion.
- A retained consequential trade record under a legal/audit exception discloses which fields are retained and why, rather than silently ignoring the deletion request.
- Export-before-delete is offered where DS-DAT-002 export is supported.
- Deletion status is reported (pending/completed/failed); a failure states the reason.
- No log entry produced by a deletion action reproduces the deleted private content — only identifier, timestamp, and outcome.

**Edge Cases:** A deletion request affecting a JournalEntry referenced by an active, unresolved TradingThesis (DS-DB-031) resolves the reference gracefully (per DS-DAT-004's referencing-record pattern) rather than corrupting the thesis record.

**Implementation Notes:** DS-004 (DS-ARC-027) owns the architectural deletion/propagation mechanism; DS-005 (DS-DB-032/033) owns the schema-level constraints; DS-008 governs secure-deletion/cryptographic-erasure implementation where the underlying storage requires it.

**Testing:** Deletion-propagation regression test (entry, attachments, derived reviews, Sage drafts); immutable-record-preservation test confirming Transaction/AuditLogEntry references survive a journal deletion; export-before-delete test; deletion-failure disclosure test; privacy-safe-logging audit confirming no deleted content appears in logs.
