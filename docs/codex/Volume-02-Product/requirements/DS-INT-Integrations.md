# DS-INT — Integrations

| Field | Value |
|---|---|
| Document ID | DS-INT |
| Title | Integrations |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md). Requirement conventions defined in DS-002 §5.

## Requirements

### DS-INT-001 — External Data Provider Boundary

**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Prevent DarkSage's market-data capability from becoming inseparably coupled to one vendor's API.

**Description:** DarkSage shall integrate external market data providers behind an internal abstraction boundary such that a provider can be added, replaced, or removed without changing product-level requirements (DS-MKT).

**Dependencies:** DS-MKT-001; DS-PRD-001

**Acceptance Criteria:**
- No Committed/MVP DS-MKT requirement's acceptance criteria name a specific vendor as a mandatory dependency.
- Adding a second provider does not require rewriting DS-MKT requirement text, only configuration/implementation.

**Edge Cases:**
- A provider-specific field with no equivalent in another provider is marked optional/extension data, not a required normalized field.

**Implementation Notes:** DS-004/DS-006 concern for the abstraction contract.

**Testing:** Provider-substitution test (swap fixture provider implementations, confirm DS-MKT behavior unchanged).

### DS-INT-002 — Credential-Based Integration Configuration

**Priority:** High | **Release Classification:** Committed / MVP | **Status:** Draft

**Purpose:** Let users connect external services explicitly and understand what they've connected.

**Description:** DarkSage shall require explicit user configuration (including any required credentials) before an external integration becomes active, and shall make active integrations visible to the user.

**Dependencies:** DS-SEC; DS-DAT-001

**Acceptance Criteria:**
- No external integration activates without an explicit configuration step attributable to the user.
- A settings surface lists currently active integrations and allows their removal/deactivation.
- Deactivating an integration stops its data flow without requiring a full application reinstall/reset.

**Edge Cases:**
- An integration whose credentials become invalid (e.g., expired token) is shown as degraded/inactive rather than silently failing without indication.

**Implementation Notes:** DS-008 concern for credential storage/security.

**Testing:** Integration activation/deactivation regression test; invalid-credential disclosure test.

### DS-INT-003 — Manual Brokerage/Execution Connectivity

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Purpose:** Record the boundary between portfolio tracking and any future manual, user-confirmed order placement, pending an owner decision on timing.

**Description:** DarkSage should allow connection to a brokerage account for the purpose of importing positions/transactions (DS-DAT-002); any manual, per-order, user-confirmed trade placement through a connected brokerage is Planned pending the owner decision recorded in DS-002 Appendix A (Open Question #2), and remains subject to DS-PRD-007's prohibition on autonomous execution regardless of timing.

**Dependencies:** DS-PRD-007; DS-DAT-002; DS-002 Appendix A

**Acceptance Criteria:**
- Read-only brokerage import (positions/transactions) does not require order-placement capability to function.
- Any future order-placement integration requires per-order explicit user confirmation (DS-PRD-005) and is not introduced without the governing owner decision.

**Edge Cases:** None recorded beyond the referenced dependencies at this classification level.

**Implementation Notes:** Full execution-integration architecture requires its own ADR and DS-006/DS-008 review before implementation.

**Testing:** Not applicable to order placement until promoted; read-only import test covered under DS-DAT-002.

### DS-INT-006 — Discord Notification Integration

**Priority:** Medium | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall implement Discord behind a notification-provider adapter supporting webhook delivery and, only when approved, a bot integration. The adapter shall expose health, test, rate-limit, retry, redaction, and revocation behavior and shall not expose execution-engine credentials or trading-control methods.
