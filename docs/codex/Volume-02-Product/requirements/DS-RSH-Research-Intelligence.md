# DS-RSH — Research Intelligence

| Field | Value |
|---|---|
| Document ID | DS-RSH |
| Title | Research Intelligence |
| Version | 0.1.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

Parent: [DS-002 — Software Requirements Specification](../DS-002-SRS.md).

## Requirements

### DS-RSH-001 — Evidence-Governed Research Record
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall represent material research items with source identity, publication/event time, retrieval time, affected symbols/entities, evidence type, freshness, confidence, and licensing/usage metadata where required.

**Acceptance Criteria:** Research summaries can trace material claims to stored source records; inferred conclusions are labeled separately; stale or conflicting sources remain visible.

### DS-RSH-002 — Multi-Source Research Domains
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall support provider-neutral ingestion and analysis of approved news, SEC/company filings, earnings materials, analyst revisions, macroeconomic events, insider transactions, institutional evidence, and publicly disclosed political trades.

**Acceptance Criteria:** Each domain can be enabled or disabled independently; absence of one domain does not masquerade as complete research coverage.

### DS-RSH-003 — Catalyst and Event Timeline
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall organize material events into a time-ordered company/market timeline and expose expected catalysts, known dates, uncertainty, and post-event updates.

### DS-RSH-004 — Thesis Monitoring
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** Users and Sage shall be able to define a thesis with supporting evidence, contradictions, assumptions, invalidation conditions, and review triggers; DarkSage shall surface material changes without silently rewriting the original thesis.

### DS-RSH-005 — Source Credibility and Conflict Disclosure
**Priority:** Critical | **Release Classification:** Planned | **Status:** Draft

**Description:** DarkSage shall disclose source quality, provenance, meaningful disagreement, and missing evidence rather than collapsing conflicting research into false consensus.

### DS-RSH-006 — Bounded Sage Research Workflow
**Priority:** High | **Release Classification:** Planned | **Status:** Draft

**Description:** Sage may perform approved multi-step research using enabled tools, maintain a visible task plan and evidence set, invoke deterministic analysis services, and produce a reviewable research package; Sage shall not use research workflow authority to bypass risk or execution controls.
