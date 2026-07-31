# DS-OPS — Reliability, Observability & Operations

| Field | Value |
|---|---|
| Document ID | DS-OPS |
| Title | Reliability, Observability & Operations |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5.

## Requirements

### DS-OPS-001 — Application Logging

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Give users and future auditors a diagnostic record of material application events without exposing sensitive data.

**Description:** DarkSage shall log material application events (startup, ingestion failures, Risk Engine determinations, crashes) locally, excluding secrets per DS-SEC-001.

**Dependencies:** DS-SEC-001; DS-PRD-010; DS-RSK-001

**Future Enhancements (Planned, not part of this requirement's Committed/MVP scope):** Once Sage/AI providers exist (DS-AI-006, Planned/Phase 6), their outages/degradation events are logged as an additional material event category under this same requirement's pattern — not a new obligation, but not required for this requirement's current acceptance since no AI provider exists yet to have an outage.

**Acceptance Criteria:**
- Each material event category listed above produces a log entry with timestamp and sufficient context for diagnosis.
- No log entry contains a raw credential/secret value (DS-SEC-001).
- Logs are locally accessible to the user/administrator without requiring an external service.

**Edge Cases:**
- Logging failure itself (e.g., disk full) is handled without crashing the primary application function it would have logged.

**Implementation Notes:** DS-004/DS-008 concern for log storage/rotation.

**Testing:** Log-content audit per material event category, including a secret-redaction check.

### DS-OPS-002 — Auditability of Risk and Sage Determinations

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Make the Sage/Risk Engine boundary (DS-PRD-006, ADR-002) independently auditable after the fact, not just enforced in the moment.

**Description:** DarkSage shall log Risk Engine determinations and any Sage output that references or is affected by a Risk Engine determination, sufficient to reconstruct the sequence of events for audit.

**Dependencies:** DS-PRD-006; DS-OPS-001

**Acceptance Criteria:**
- A Risk Engine block/warning and any related Sage output are both logged with correlated timestamps, enabling reconstruction of the interaction.
- Audit logs for these events are retained per a documented minimum retention period distinct from general application logs.

**Edge Cases:**
- Concurrent Risk Engine events (e.g., multiple positions breaching limits near-simultaneously) are individually distinguishable in the audit log, not merged into one ambiguous entry.

**Implementation Notes:** DS-004/DS-008/DS-009 concern for audit-log architecture and retention policy.

**Testing:** Audit-reconstruction test: given a logged interaction sequence, confirm the Risk Engine/Sage sequence of events can be accurately reconstructed.

### DS-OPS-003 — Understandable Error Handling

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Prevent errors from leaving users confused about what happened or what to do next, per DS-001 §19.

**Description:** DarkSage shall present user-facing errors in plain language describing what happened and, where applicable, what the user can do next, rather than exposing raw technical error output as the primary message.

**Dependencies:** DS-001 §19

**Acceptance Criteria:**
- A Committed/MVP error surface presents a plain-language description; raw technical detail (stack trace, error code) is available on request/expansion, not as the primary message.
- An error does not silently fail (no visible indication) for any Committed/MVP user-initiated action.

**Edge Cases:**
- A transient error (e.g., temporary network blip) is distinguished from a persistent error requiring user action.

**Implementation Notes:** DS-007 concern for error presentation patterns.

**Testing:** Error-message content audit across a fixture set of Committed/MVP failure scenarios.

### DS-OPS-004 — Offline and Degraded Operation

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Preserve local-first value even when external dependencies are unavailable, per DS-001 §14 and DS-PRD-010.

**Description:** DarkSage shall remain usable for local-only capability (workspace use, locally stored data, deterministic calculations on local data) when network connectivity or external services are unavailable, disclosing which capabilities are degraded.

**Dependencies:** DS-PRD-010; DS-DAT-001

**Acceptance Criteria:**
- Loss of network connectivity does not block access to local-only Committed/MVP capability.
- Degraded/unavailable capability is disclosed to the user rather than silently failing (consistent with DS-OPS-003).
- Reconnection restores affected capability without requiring an application restart.

**Future Enhancements (Planned, not part of this requirement's Committed/MVP scope):** Once Sage/AI providers exist (DS-AI-006, Planned/Phase 6), AI degradation/unavailability follows this same disclosure pattern under DS-AI-006's own requirement — not a new obligation, and not required for this requirement's current acceptance.

**Edge Cases:**
- A feature requiring both local and external data (e.g., a chart needing a live quote) degrades to its last-known/local data with disclosure, rather than becoming entirely unavailable.

**Implementation Notes:** DS-004 concern for offline-mode architecture.

**Testing:** Simulated network-loss regression test confirming local capability remains usable and degraded state is disclosed.
