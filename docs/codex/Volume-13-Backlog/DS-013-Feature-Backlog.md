# DS-013 — Feature Backlog

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-013 |
| Title | Feature Backlog |
| Version | 0.3.2 |
| Status | Draft |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-24 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| 0.1.0 | 2026-07-24 | TheSinnerMan | First controlled draft, authored as part of the final grouped batch (DS-013/DS-014). Establishes the backlog governance model (`DS-BLG-NNN`) and a structured catalog of 26 candidate features (`DS-BL-NNN`) not yet part of the committed implementation baseline, drawn from prior product discussion and this Codex's own DS-001–012 direction. |
| 0.2.0 | 2026-07-24 | TheSinnerMan | Targeted repair for three independent-audit High findings, plus one Founder-approved addition. **H1 (promotion lifecycle):** `DS-BLG-002`'s status taxonomy expanded from seven to **eight** values, adding **Promoted** as a terminal/transition-record status (never equivalent to implemented, released, or completed); `DS-BLG-003` updated so a valid promotion identifies both its destination authority (requirement/roadmap-item/ADR/implementation issue) and its promotion decision. **H2 (public Owner Approval authority):** `DS-BLG-004`'s Owner Approval flag no longer cites `.ai-workflow/KEEPER_AUTHORITY.md`; grounded instead in DS-012's public, reproducible approval model (DS-ADR-003) and DS-010's normative process rules (DS-DEV-025) — a local workflow file, if mentioned at all, is non-authoritative operational convenience only. **H3 (third-party model gates):** `DS-BL-018`, `DS-BL-020` (Kronos), and `DS-BL-021` updated to require all nine of DS-014's `DS-IDG-004` mandatory gates (licensing, independent benchmarking, compute requirements, privacy, security, model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, operational feasibility) before promotion, aligned with DS-008. **Addition:** new `DS-BL-027` — Responsive Loading and Interaction Feedback (§6.15), a Founder-approved backlog item defining skeleton loaders, caching, optimistic rendering for reversible actions only, and contextual tooltips, with an explicit Hard Safety Boundary prohibiting optimistic rendering for trades, broker actions, risk/permission changes, emergency controls, credentials, authentication, strategy promotion, and authoritative account state. Catalog is now 27 items. |
| 0.3.0 | 2026-07-24 | TheSinnerMan | Final targeted repair closing the remaining High finding: the promotion lifecycle was still internally inconsistent after v0.2.0. **Scope taxonomy:** §2 Scope now lists all eight statuses explicitly (previously omitted Promoted); §1 Purpose, §2 Scope, §4 Definitions, `DS-BLG-002`, and `DS-BLG-003` now consistently define exactly eight. **Authoritative promotion destination:** an implementation-tracking issue is no longer accepted as a co-equal, standalone promotion destination — it may only be linked as a subordinate execution-tracking artifact beneath an already-approved **controlling authority** (a dedicated DS-002+ requirement, an approved DS-011 roadmap entry, an approved DS-012 ADR, or another explicitly recognized committed Codex authority), and it must itself cite that controlling authority by ID. **Terminology:** replaced "the requirement becomes authoritative" with "the promoted capability receives authority only from its approved controlling destination" throughout; added `Controlling authority`, `Promoted capability`, and `Implementation-tracking issue` to §4 Definitions, clearly distinguishing backlog item / promoted capability / controlling authority / implementation-tracking issue. **Promotion record:** `DS-BLG-003` now specifies a complete promotion record (source ID, controlling destination ID, destination type, approval authority/mechanism, approval date, decision record or evidence, optional implementation-tracking issue, bidirectional cross-reference where supported). **Acceptance criteria:** `DS-BLG-002`/`DS-BLG-003` updated so verification can prove all eight statuses are consistent, every Promoted item has an approved controlling authority, no implementation issue is standalone authority, every linked implementation issue cites its controlling authority, and Promoted never equals implemented/released/completed. |
| 0.3.1 | 2026-07-24 | TheSinnerMan | Mechanical wording repair. Added a dedicated **Canonical Backlog Status Taxonomy** subsection near the top of the document, stating the exact eight-status list (spelling, capitalization, spacing, and slash formatting normative) and declaring it canonical for §1, §2, §4, `DS-BLG-002`, and `DS-BLG-003`. All five locations now **explicitly** adopt this taxonomy by name (previously implied, not stated). Normalized the incorrect unspaced-slash form in §2 to the exact canonical `Rejected / Not Pursuing`. Added `deployed` to every operative Promoted non-equivalence statement (§4 "Promoted capability," `DS-BLG-002`, `DS-BLG-003` description and acceptance criteria), which previously listed only `implemented, released,` and `completed`/`complete` — now all four terms (`implemented, released, completed, or deployed`) appear consistently. `DS-BLG-002`'s acceptance criteria now explicitly forbid alternate spelling/slash formatting/abbreviation/synonym for any of the eight labels. |
| 0.3.2 | 2026-07-24 | TheSinnerMan | Consolidated cleanup pass, non-blocking items only. `DS-BL-013`'s Promotion Criteria now states five explicit required properties (non-manipulative, user-controlled, optional, transparent, subordinate to product safety/user welfare) any future gamification requirement must satisfy — clarifies the DS-001 anti-engagement-optimization tension without approving or rejecting the item, which remains Candidate. Added a §4 Definitions entry distinguishing backlog status "Planned" (DS-BLG-002) from DS-002 §5.3 Release Classification "Planned," making explicit a terminology collision the two documents previously left implicit. Added reciprocal, explicitly-non-counterpart cross-references from `DS-BL-007`/`DS-BL-015`/`DS-BL-016` to the DS-014 ideas (`DS-IDEA-012`/`DS-IDEA-016`/`DS-IDEA-015` respectively) that already cited them one-directionally as "related," so the relationship reads consistently from both documents without implying duplicate scope. No status, classification, or approved decision was changed. |

## Canonical Backlog Status Taxonomy

DS-013 defines exactly eight backlog statuses:

- Approved Future
- Planned
- Candidate
- Deferred
- Blocked
- Research Needed
- Rejected / Not Pursuing
- Promoted

This list is canonical. All references to backlog status in this volume, including §1 Purpose, §2 Scope, §4 Definitions, DS-BLG-002, and DS-BLG-003, adopt this exact taxonomy and terminology. No alternate spelling, slash formatting, abbreviation, or synonym for any of these eight labels is normative.

## 1. Purpose

DS-013 is the authoritative structured backlog for DarkSage features that are not part of the current committed implementation baseline. It tracks candidate capabilities for future evaluation and planning. §1 adopts the **Canonical Backlog Status Taxonomy** defined above in full: every `DS-BL-NNN` backlog item's Status is exactly one of Approved Future, Planned, Candidate, Deferred, Blocked, Research Needed, Rejected / Not Pursuing, or Promoted. **Inclusion in this backlog is never itself an approval for implementation** — a `DS-BL-NNN` backlog item becomes a promoted capability only when an approved controlling authority (a dedicated DS-002+ requirement, an approved DS-011 roadmap entry, or an approved DS-012 ADR) is separately authored for it through the normal Codex-Driven Development process (DS-001 Constitution #12). **The promoted capability receives authority only from its approved controlling destination — the backlog entry itself never becomes authoritative, and neither does a bare implementation-tracking issue** (DS-BLG-003).

## 2. Scope

This document governs: the backlog status taxonomy — §2 adopts the **Canonical Backlog Status Taxonomy** in full and exactly: Approved Future, Planned, Candidate, Deferred, Blocked, Research Needed, Rejected / Not Pursuing, Promoted (eight statuses, no more and no fewer); the promotion process from backlog item to an approved controlling authority (a dedicated DS-002+ requirement, an approved DS-011 roadmap entry, or an approved DS-012 ADR), with an implementation-tracking issue permitted only as a subordinate execution-tracking artifact beneath such an authority, never as a standalone promotion destination; the review-gate flag vocabulary (architecture, security, legal/compliance, market-data licensing, owner approval, model benchmarking, cost evaluation); and the structured catalog of currently known candidate features.

DS-013 does not govern: committed or Planned product requirements (DS-002 through DS-009 remain authoritative once an item is promoted); roadmap phase sequencing (DS-011); architecture decisions (DS-012, ADR-001–004); or speculative/research-stage ideas not yet understood well enough to track as a potential product capability (DS-014 — see §5's boundary rule, DS-BLG-006).

## 3. Audience

Product owners, engineering contributors, independent auditors, and future Codex authors evaluating or promoting candidate features.

## 4. Definitions

See DS-001 §24 and DS-002 §4. Additional terms:

| Term | Meaning |
|---|---|
| Canonical Backlog Status Taxonomy | §4 adopts, in full and exactly, the eight-status list defined in **Canonical Backlog Status Taxonomy** above: Approved Future, Planned, Candidate, Deferred, Blocked, Research Needed, Rejected / Not Pursuing, Promoted. Every status reference elsewhere in this document — §1, §2, DS-BLG-002, DS-BLG-003, and every `DS-BL-NNN` item's Status field — uses these exact eight labels; no alternate spelling, slash formatting, abbreviation, or synonym is normative |
| Backlog item | A candidate feature tracked for future evaluation or planning, carrying no Release Classification (Committed/MVP, Planned, Future/Exploratory) of its own — that classification exists only for its approved controlling destination once promoted, never for the backlog entry itself |
| Backlog status "Planned" vs. Release Classification "Planned" | Two distinct, non-interchangeable governance concepts that happen to share the word "Planned." A `DS-BL-NNN` item's **backlog status** of Planned (DS-BLG-002) means the item elaborates or extends a topic whose DS-002+ requirement family already exists and is itself Release-Classified Planned (DS-002 §5.3) — the backlog item tracks *scope beyond* that family, never a duplicate of it, and still carries no Release Classification of its own (per the Backlog item definition above). A requirement's **Release Classification** of Planned (DS-002 §5.3) is a property of an approved, authored DS-002+ requirement itself. Citing a backlog item's Planned status is never sufficient to establish or imply that any requirement holds Release Classification Planned, and vice versa — the two vocabularies are read separately, never substituted for each other |
| Promotion | The act of authoring an approved controlling authority (a dedicated DS-002+ requirement, an approved DS-011 roadmap entry, or an approved DS-012 ADR) for a backlog item through the normal Codex-Driven Development process, after which the backlog item's Status changes to Promoted and a promotion record is created (DS-BLG-003) |
| Controlling authority | The approved, committed destination that gives a promoted capability its authority: a dedicated DS-002+ requirement, an approved DS-011 roadmap entry, an approved DS-012 ADR, or another explicitly recognized committed Codex authority already defined by public governance — never a bare backlog entry and never an implementation-tracking issue alone |
| Promoted capability | A backlog item whose Status is Promoted; it is authoritative only through its cited controlling authority, never in its own right. Promoted does not mean implemented, released, completed, or deployed |
| Implementation-tracking issue | An optional execution-tracking artifact (e.g., a repository issue) that may be linked beneath an already-approved controlling authority to track implementation progress; it never itself establishes product authority and is not a valid promotion destination on its own — it must cite its controlling authority by ID |
| Review-gate flag | A marker on a backlog item identifying a specific review or evaluation (architecture, security, legal/compliance, market-data licensing, owner approval, model benchmarking, cost evaluation) required before promotion |

## 5. Backlog Governance

### DS-BLG-001 — Backlog Purpose and Non-Promotion Rule

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-001 §11 (Constitution #12); DS-RM-012 (DS-011, Committed)

**Description:** Inclusion of an item in this backlog means "tracked for evaluation or future planning," never "approved for implementation." No `DS-BL-NNN` item carries a Release Classification of its own, and no downstream document may cite backlog inclusion as evidence that a capability is Committed, Planned, or otherwise authorized. This mirrors DS-RM-012's identical rule for `ROADMAP.md` phase-listed deliverables — presence in a phase list or a backlog never itself promotes an item.

**Acceptance Criteria:**
- No DS-002 through DS-012 requirement cites a `DS-BL-NNN` ID as its Governing Source for Committed or Planned status.
- No backlog item's own entry in this document states or implies a Release Classification.

**Testing:** Requirements-review check confirming no backlog-only mention is treated as a committed or Planned requirement (shared with DS-RM-012's own test).

### DS-BLG-002 — Backlog Status Taxonomy

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-013 (this document, normative); **Canonical Backlog Status Taxonomy** (adopted in full and exactly)

**Description:** Every backlog item carries exactly one Status, drawn from the **Canonical Backlog Status Taxonomy** defined above:

- **Approved Future** — direction already approved at the DS-001/`ROADMAP.md` level (e.g., named in a `ROADMAP.md` phase) but not yet authored as its own dedicated DS-002+ requirement.
- **Planned** — a further elaboration or extension of a topic where a DS-002+ requirement family already exists and is itself classified Planned (DS-002 §5.3); the backlog item tracks scope beyond that family's current requirements, not a duplicate of them.
- **Candidate** — identified and described, but not yet evaluated or approved for any direction; requires product/owner review before further classification.
- **Deferred** — acknowledged and intentionally not pursued in the near term, pending a stated trigger (e.g., a later roadmap phase, an owner decision, or a prerequisite capability).
- **Blocked** — cannot proceed until a specific named dependency, review, or decision resolves.
- **Research Needed** — requires research, benchmarking, or technical evaluation before a productization decision can be made; frequently cross-references a DS-014 idea holding the research concept.
- **Rejected / Not Pursuing** — evaluated and explicitly declined, with the reason recorded; retained in the backlog as a decision record, not deleted.
- **Promoted** — a terminal/transition-record status showing the backlog item has become a **promoted capability**: an approved **controlling authority** now exists for it — a dedicated DS-002+ requirement, an approved DS-011 roadmap entry, an approved DS-012 ADR, or another explicitly recognized committed Codex authority already defined by public governance (DS-BLG-003). **The promoted capability receives authority only from its approved controlling destination — never from the backlog entry itself, and never from an implementation-tracking issue alone.** An implementation-tracking issue (e.g., a repository issue tracking execution) may optionally be linked beneath the controlling authority once one exists, but never substitutes for one. **Promoted does not mean implemented, released, completed, or deployed** — the controlling authority's own status (e.g., a DS-002 requirement's Release Classification) governs whether the underlying work is actually done.

**Acceptance Criteria:**
- Every `DS-BL-NNN` item's Status field uses exactly one of these **eight** values (Approved Future, Planned, Candidate, Deferred, Blocked, Research Needed, Rejected / Not Pursuing, Promoted), matching its own stated Rationale/Notes.
- The eight statuses listed above match the **Canonical Backlog Status Taxonomy** exactly — same count, same order, same labels, same spelling, capitalization, spacing, and slash formatting (`Rejected / Not Pursuing` with spaces around the slash).
- No alternate spelling, unspaced-slash formatting, abbreviation, or synonym for any of the eight labels is normative anywhere in this document.

**Testing:** Status-taxonomy conformance check across all backlog items on every DS-013 revision, including an exact-string check against the Canonical Backlog Status Taxonomy.

### DS-BLG-003 — Promotion Process

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-001 §11 (Constitution #12); DS-RM-002 (DS-011, Committed); DS-ADR-008 (DS-012, Committed)

**Description:** DS-BLG-003 adopts the **Canonical Backlog Status Taxonomy** defined by DS-BLG-002 (and the canonical taxonomy subsection at the top of this document) in full: `Promoted` is one of the eight statuses in that taxonomy (Approved Future, Planned, Candidate, Deferred, Blocked, Research Needed, Rejected / Not Pursuing, Promoted), and this requirement states the process by which a backlog item's Status becomes Promoted specifically. A backlog item is promoted by authoring its own approved **controlling authority**: a dedicated DS-002+ requirement (classified per DS-RM-002's phase-to-classification mapping test), an approved DS-011 roadmap entry, an approved DS-012 ADR (where the decision is material, durable, and cross-cutting per DS-ADR-008), or another explicitly recognized committed Codex authority already defined by public governance — through the normal author → self-verify → independent audit → approval process this Codex already uses. **An implementation-tracking issue is never itself a controlling authority and never justifies Promoted status on its own.** It may only be linked as a subordinate execution-tracking artifact beneath an already-approved controlling authority, and it must itself cite that controlling authority by ID.

Upon promotion, the backlog item's Status changes to Promoted, and a **promotion record** is created identifying:
- the source `DS-BL-NNN` ID;
- the approved controlling destination ID;
- the destination type (DS-002+ requirement, DS-011 roadmap entry, DS-012 ADR, or another recognized committed Codex authority);
- the approval authority/mechanism (e.g., Owner approval, an explicitly delegated approver within documented scope, or the Codex's own audit/approval process);
- the approval date;
- a decision record or evidence (e.g., the destination's own Decision History entry, a commit reference, or an equivalent committed record);
- an optional implementation-tracking issue, if one exists, which must itself cite the controlling authority; and
- a bidirectional cross-reference where the destination document supports one (e.g., the DS-002+ requirement or ADR citing this `DS-BL-NNN` ID back).

A bare Status change with no controlling destination or promotion record is not a valid promotion. **The promoted capability receives authority only from its approved controlling destination — the backlog entry itself never becomes authoritative, and neither does any linked implementation-tracking issue.** **Promoted does not mean implemented, released, completed, or deployed** (DS-BLG-002). Promotion is never performed by editing this document's Status field alone without the corresponding controlling authority existing.

**Acceptance Criteria:**
- `Promoted` is confirmed as one of the exact eight statuses in the Canonical Backlog Status Taxonomy (DS-BLG-002) — not a status this requirement defines independently.
- No backlog item is marked Promoted without a corresponding, existing controlling authority (DS-002+ requirement, DS-011 entry, DS-012 ADR, or another explicitly recognized committed Codex authority) cited by ID and destination type.
- No backlog item is marked Promoted without a complete promotion record: source ID, destination ID, destination type, approval authority/mechanism, approval date, and decision record or evidence.
- No implementation-tracking issue is ever treated as a standalone controlling authority; an implementation-tracking issue never appears as a promotion's sole cited destination.
- Every implementation-tracking issue linked to a promoted item cites its own controlling authority by ID.
- A promoted item's original backlog entry remains in this document (not deleted) as a historical record, cross-referencing its controlling destination, with a bidirectional cross-reference where the destination document supports one.
- No Promoted item's entry states or implies that the underlying capability is implemented, released, completed, or deployed — only that it has an approved controlling authority.

**Testing:** Promotion-record audit: every Promoted-status item's cited controlling-authority ID exists, traces back to this backlog item, carries a complete promotion record, and — where an implementation-tracking issue is linked — that issue itself cites the controlling authority.

### DS-BLG-004 — Review-Gate Flags

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-013 (this document, normative); DS-008 (Committed); `SECURITY_RULES.md`

**Description:** A backlog item may carry one or more review-gate flags identifying evaluation required before promotion: **Architecture** (DS-004/DS-012 design work needed), **Security** (DS-008 review required, e.g., a new external integration or credential surface), **Legal/Compliance** (regulatory or licensing exposure, e.g., political-trading data or tax features), **Market-Data Licensing** (a new data provider's licensing terms must be evaluated), **Owner Approval** (a decision requiring the repository Owner's authority, or an explicitly delegated approver acting within documented scope with the approval recorded as reproducible evidence in a committed record — per DS-ADR-003's (DS-012) public approval-authority model, e.g., material product-scope expansion or paid-service commitment), **Model Benchmarking** (an AI/ML capability requiring measured evaluation before adoption, per DS-QA-011's model-evaluation discipline), and **Cost Evaluation** (recurring-cost impact requiring Cheap-First Architecture review, `PROJECT_SPEC.md` §2.1). This flag's authority is grounded in DS-012's public, reproducible approval model (DS-ADR-003) and DS-010's normative process rules (DS-DEV-025) — a local, non-committed workflow file, where one exists, may serve only as non-authoritative operational convenience describing how a specific approval was reached locally; it is never itself the source of Owner Approval authority, and a future reader relying solely on committed repository content must be able to reproduce this boundary in full without it.

**Acceptance Criteria:**
- Every backlog item likely to require one of these reviews states the applicable flag(s) explicitly in its own entry; a flag is never silently dropped between revisions without the underlying review having occurred.
- No Owner Approval determination is evidenced solely by a local, non-committed file; DS-ADR-003's committed-record requirement (Decision History or equivalent) applies wherever an Owner Approval flag is resolved through an ADR, and an equivalent committed record applies otherwise.

**Testing:** Review-gate flag completeness check against each item's stated Risks/Open Questions; approval-record audit (shared with DS-ADR-003's own test) for any item whose Owner Approval flag has been resolved.

### DS-BLG-005 — Relationship to DS-011 and DS-012

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-ADR-001, DS-ADR-010 (DS-012, both Committed); DS-RM-001 (DS-011, Committed)

**Description:** A backlog item never overrides `ROADMAP.md`'s phase content or an Approved ADR's decision. A backlog item whose promotion would require a material, durable, cross-cutting decision (DS-ADR-008's bar) is promoted through a new ADR first, not directly into a DS-002+ requirement that assumes the decision. A backlog item's Governing Source, where it cites a `ROADMAP.md` phase, is checked against DS-011's Phase Reference Table (DS-011 §6) for consistency.

**Acceptance Criteria:** No backlog item's Rationale or Promotion Criteria contradicts an Approved ADR or `ROADMAP.md`'s stated phase content.

**Testing:** Cross-volume contradiction check against DS-011/DS-012 on every DS-013 revision.

### DS-BLG-006 — Relationship to DS-014 (Boundary Rule)

**Release Classification:** Committed / MVP (governance) | **Governing Source:** DS-013 (this document, normative); DS-IDG-005 (DS-014, Committed)

**Description:** DS-013 holds a feature once it is understood enough to track as a potential product capability (a defined scope, a plausible Product Area, and at least a preliminary Rationale). DS-014 holds the earlier-stage research concept, speculative direction, or technical exploration behind a feature that is not yet that well-defined. Where a topic exists in both — most of this Codex's AI/model-research items — DS-013 holds the productized candidate (e.g., "Specialized Local Financial Models," DS-BL-018) and DS-014 holds the underlying research concept (e.g., "DarkSage Market Foundation Model," DS-IDEA-001), each explicitly cross-referencing the other by ID. Neither document restates the other's content as a second authority.

**Acceptance Criteria:**
- No feature concept is fully duplicated with independent, non-cross-referenced content in both DS-013 and DS-014.
- Every DS-013 item that has a DS-014 counterpart cites it by ID, and vice versa.

**Testing:** Cross-volume duplication check between DS-013 and DS-014 on every revision of either document.

## 6. Backlog Catalog

Each item states: ID, Title, Summary, Status, Priority (evaluation priority, not implementation urgency — Critical/High/Medium/Low per DS-002 §5.4's scale), Product Area, Governing Source, Dependencies, Rationale, Acceptance/Promotion Criteria, Risks, Open Questions, Related Volumes/ADRs, and Notes.

### 6.1 Trading and Execution

#### DS-BL-001 — Live Trading Progression Beyond Phase 13

- **Summary:** Expansion of live-trading allocation tiers and strategy eligibility beyond `ROADMAP.md` Phase 13's initial "very small allocation" tier, toward Phase 14's full-auto mode for approved strategies.
- **Status:** Approved Future | **Priority:** High | **Product Area:** Trading & Execution
- **Governing Source:** `ROADMAP.md` Phase 13/14; DS-EXE-007 (Committed governance boundary)
- **Dependencies:** DS-BL-025 (Future Live Execution Controls); DS-RM-006 (Gate-chain)
- **Rationale:** Already-approved product direction (`ROADMAP.md` explicitly sequences Phase 13 → 14); not yet its own dedicated set of DS-002 requirements beyond DS-EXE-007's governance boundary.
- **Promotion Criteria:** Requires dedicated DS-002 requirements for each allocation-tier transition rule, each promotion/demotion rule, and DS-EXE-007's full prerequisite list satisfied per phase.
- **Risks:** Real capital exposure; premature promotion would violate DS-SCA-022's live-trading review gate.
- **Open Questions:** Allocation-tier thresholds not yet defined.
- **Related Volumes/ADRs:** DS-002 (DS-EXE), DS-008 (DS-SCA-022), DS-011 (DS-RM-006), ADR-002.
- **Review Gates:** Owner Approval, Security.
- **Notes:** None.

#### DS-BL-002 — Broker Adapter Expansion

- **Summary:** Additional broker adapters beyond the initial PaperBroker/first live adapter, following the Broker Adapter abstraction.
- **Status:** Planned | **Priority:** Medium | **Product Area:** Trading & Execution
- **Governing Source:** DS-EXE-006 (Planned, Phase 7); `ROADMAP.md` Phase 14 ("Additional broker adapters where justified")
- **Dependencies:** DS-EXE-006's own implementation (Phase 7)
- **Rationale:** The adapter pattern already anticipates multiple brokers; specific additional brokers are not yet named or evaluated.
- **Promotion Criteria:** A specific broker is named, its API/cost/reliability evaluated, and a dedicated DS-EXE requirement authored.
- **Risks:** Broker-specific integration risk; reconciliation complexity per broker.
- **Open Questions:** Which broker(s) beyond the first are justified.
- **Related Volumes/ADRs:** DS-002 (DS-EXE), DS-004 (DS-ARC-006 pattern).
- **Review Gates:** Architecture, Security, Cost Evaluation.
- **Notes:** None.

#### DS-BL-025 — Future Live Execution Controls

- **Summary:** Additional execution-control refinements beyond Emergency Stop/Flatten — e.g., partial-position de-risking, per-strategy kill switches, graduated risk throttling.
- **Status:** Approved Future | **Priority:** Medium | **Product Area:** Trading & Execution
- **Governing Source:** `ROADMAP.md` Phase 14; DS-SCA-016 (Planned, Phase 7)
- **Dependencies:** DS-EXE-004/005 (Emergency Stop/Flatten) implemented first
- **Rationale:** Phase 14's "Live execution analytics," "Order-type intelligence" direction implies control refinements beyond the Phase-7 baseline.
- **Promotion Criteria:** Each control is authored as its own DS-EXE requirement once Phase-7 baseline controls are proven.
- **Risks:** Additional control surface increases the security-critical code footprint (DS-SCA-021's independent-review requirement applies to each).
- **Open Questions:** Specific control set not yet defined.
- **Related Volumes/ADRs:** DS-002 (DS-EXE), DS-008 (DS-SCA-016/021).
- **Review Gates:** Architecture, Security, Owner Approval.
- **Notes:** None.

### 6.2 Market Data and Providers

#### DS-BL-003 — Additional Market-Data and Chart Providers

- **Summary:** Additional market-data and charting data providers beyond the initial provider, using the existing Market Data Provider Abstraction.
- **Status:** Approved Future | **Priority:** Medium | **Product Area:** Market Data
- **Governing Source:** DS-ARC-006 (Committed, provider-adapter pattern)
- **Dependencies:** None beyond DS-ARC-006 already existing
- **Rationale:** The adapter pattern is Committed and designed for this; specific additional providers are not yet named.
- **Promotion Criteria:** A specific provider is named, licensing/cost evaluated, and a dedicated DS-MKT/DS-INT requirement authored.
- **Risks:** Data-quality inconsistency across providers if normalization is incomplete.
- **Open Questions:** Which provider(s) are justified beyond the initial one.
- **Related Volumes/ADRs:** DS-002 (DS-MKT, DS-INT), DS-004 (DS-ARC-006).
- **Review Gates:** Market-Data Licensing, Cost Evaluation.
- **Notes:** None.

### 6.3 Scanner and Signals

#### DS-BL-004 — Advanced Scanner Expansion

- **Summary:** Scanner capability beyond DS-SCN-004 (AI-Assisted Scan Analysis) and DS-SCN-005 (Scan Result History) — e.g., natural-language scan construction (`ROADMAP.md` Phase 10's "Natural-language scanner builder"), saved scan sharing, cross-scan comparison.
- **Status:** Planned | **Priority:** Medium | **Product Area:** Scanner & Signals
- **Governing Source:** DS-SCN-004/005 (both Planned); `ROADMAP.md` Phase 10
- **Dependencies:** DS-SCN-001/002/003 (Committed baseline) implemented first
- **Rationale:** DS-SCN already has a Planned extension path; further expansion beyond DS-SCN-004/005's current scope is not yet its own requirement.
- **Promotion Criteria:** Specific capability authored as its own DS-SCN requirement.
- **Risks:** Natural-language scan construction depends on Sage (Phase 6) existing first.
- **Open Questions:** Scope of "advanced" not yet defined.
- **Related Volumes/ADRs:** DS-002 (DS-SCN).
- **Review Gates:** None beyond normal review.
- **Notes:** None.

### 6.4 Strategy and Backtesting

#### DS-BL-005 — Strategy Builder and Strategy Library Growth

- **Summary:** Expansion of DS-STR-001 (Strategy Construction) into a fuller strategy-authoring UI/library, including community or curated strategy templates.
- **Status:** Planned | **Priority:** Medium | **Product Area:** Strategy
- **Governing Source:** DS-STR-001/003 (both Planned)
- **Dependencies:** DS-STR-001's baseline construction capability
- **Rationale:** DS-STR already covers construction/validation/AI-assisted authoring at a Planned level; a "library" concept (shared/curated templates) is not yet a requirement.
- **Promotion Criteria:** Library/sharing model defined and authored as a dedicated DS-STR requirement, including any data-sharing privacy implications (DS-SEC-002).
- **Risks:** Shared strategy content could imply investment-advice liability if not carefully scoped as informational.
- **Open Questions:** Whether strategy sharing is user-to-user or curated-only.
- **Related Volumes/ADRs:** DS-002 (DS-STR).
- **Review Gates:** Legal/Compliance, Owner Approval.
- **Notes:** None.

#### DS-BL-006 — Deeper Backtesting and Synthetic Scenario Testing

- **Summary:** Backtesting extensions beyond DS-BKT-001–004 — e.g., synthetic/simulated market scenario generation for stress-testing strategies beyond historical data alone.
- **Status:** Candidate | **Priority:** Medium | **Product Area:** Backtesting
- **Governing Source:** DS-BKT-001 (Planned); `ROADMAP.md` Phase 8 ("Monte Carlo simulation," "Risk-of-ruin analysis")
- **Dependencies:** DS-BKT-001–004 (Planned, Phase 2) implemented first; DS-IDEA-010 (Synthetic Market Generation, DS-014) for the underlying generative technique
- **Rationale:** `ROADMAP.md` Phase 8 already names Monte Carlo simulation direction; synthetic scenario generation beyond that is not yet defined.
- **Promotion Criteria:** Synthetic-generation methodology evaluated (statistical validity per DS-BKT-003's look-ahead-bias discipline) and authored as its own DS-BKT requirement.
- **Risks:** A poorly-validated synthetic scenario could produce misleadingly optimistic backtest results, violating DS-BKT-004's disclosure requirement if not clearly labeled as synthetic (DS-PRD-008).
- **Open Questions:** Generation methodology (statistical resampling vs. generative model, DS-IDEA-010).
- **Related Volumes/ADRs:** DS-002 (DS-BKT), DS-014 (DS-IDEA-010).
- **Review Gates:** Architecture, Model Benchmarking.
- **Notes:** Cross-references DS-IDEA-010 per DS-BLG-006.

### 6.5 Asset Class Expansion

#### DS-BL-007 — Options Support

- **Summary:** Options research and trading support per `ROADMAP.md` Phase 11 (options chain, Greeks, IV, options backtesting, defined-risk strategies first; no live options trading in this phase).
- **Status:** Deferred | **Priority:** Low | **Product Area:** Asset Class Expansion
- **Governing Source:** `ROADMAP.md` Phase 11 (Future/Exploratory content per DS-RM-012)
- **Dependencies:** DS-BKT (Phase 2 backtesting infrastructure)
- **Rationale:** Explicitly a later, separate instrument system per `ROADMAP.md`; deferred until Phase 11's own dedicated requirements are authored.
- **Promotion Criteria:** Dedicated DS-002 family (e.g., a new `DS-OPT` prefix) authored per DS-RM-002's classification test once Phase 11 is reached.
- **Risks:** Options carry materially different risk profiles than equities; requires its own risk-model extension before any live capability.
- **Open Questions:** None beyond Phase 11's own scope, which is not yet authored.
- **Related Volumes/ADRs:** DS-011 (Phase 11, DS-RM-015 Optional/Deferred category); DS-014 DS-IDEA-012 (Options and Order-Flow Intelligence — related but distinct scope: DS-IDEA-012 is options/order-flow *data as market-intelligence evidence*, not options *trading*; not a counterpart of this item).
- **Review Gates:** Architecture, Security, Legal/Compliance.
- **Notes:** None.

#### DS-BL-008 — Futures Support

- **Summary:** Futures market data, analysis, and (later) trading support — not currently named in `ROADMAP.md`.
- **Status:** Research Needed | **Priority:** Low | **Product Area:** Asset Class Expansion
- **Governing Source:** None — net-new candidate, no current Codex grounding
- **Dependencies:** DS-BL-007's options infrastructure as a likely technical precedent
- **Rationale:** Raised as a plausible future asset-class expansion; not yet evaluated for product fit.
- **Promotion Criteria:** Market/data-provider research completed; a dedicated `ROADMAP.md` phase or extension approved by the owner before any DS-002 requirement is authored.
- **Risks:** Margin/leverage mechanics differ materially from equities/options; Risk Engine (DS-RSK) would need a dedicated extension.
- **Open Questions:** Whether futures fit DarkSage's target user base at all.
- **Related Volumes/ADRs:** None yet.
- **Review Gates:** Owner Approval, Legal/Compliance, Market-Data Licensing.
- **Notes:** None.

#### DS-BL-009 — Crypto Support

- **Summary:** Cryptocurrency market data, analysis, and (later) trading support — not currently named in `ROADMAP.md`.
- **Status:** Research Needed | **Priority:** Low | **Product Area:** Asset Class Expansion
- **Governing Source:** None — net-new candidate, no current Codex grounding
- **Dependencies:** None
- **Rationale:** Raised as a plausible future asset-class expansion; not yet evaluated for product fit.
- **Promotion Criteria:** Market/data-provider and custody research completed; owner approval for scope expansion; dedicated `ROADMAP.md` phase or extension before any DS-002 requirement.
- **Risks:** 24/7 market structure, custody/security model, and regulatory treatment all differ materially from equities; would require dedicated DS-008 security review before any credential/wallet handling.
- **Open Questions:** Custody model (self-custody vs. broker-custodied) entirely undecided.
- **Related Volumes/ADRs:** None yet.
- **Review Gates:** Owner Approval, Legal/Compliance, Security, Market-Data Licensing.
- **Notes:** None.

### 6.6 Market Intelligence

#### DS-BL-010 — Political-Trading Intelligence

- **Summary:** Surfacing publicly disclosed political/legislative trading activity (e.g., congressional disclosure filings) as a market-intelligence evidence source.
- **Status:** Candidate | **Priority:** Low | **Product Area:** Market Intelligence
- **Governing Source:** None — net-new candidate, no current Codex grounding
- **Dependencies:** DS-MKT (data ingestion pattern); DS-PRD-002 (evidence provenance)
- **Rationale:** Publicly discussed as a differentiated evidence source; not yet evaluated for data-source reliability or legal exposure.
- **Promotion Criteria:** Data-source reliability and disclosure-timeliness evaluated; legal review confirming no restricted-data handling; a dedicated DS-002 requirement authored with explicit provenance/staleness disclosure (DS-PRD-002/008).
- **Risks:** Disclosure-filing data is often delayed by weeks; presenting it without clear staleness labeling would violate DS-PRD-008/DS-PRD-009.
- **Open Questions:** Data source and licensing not yet identified.
- **Related Volumes/ADRs:** DS-002 (DS-PRD-002/008), DS-008.
- **Review Gates:** Legal/Compliance, Market-Data Licensing.
- **Notes:** None.

### 6.7 Auxiliary Modules

#### DS-BL-011 — Tax and Budgeting Module

- **Summary:** Tax-lot tracking, tax-aware trade suggestions, and personal budgeting features layered on portfolio data.
- **Status:** Candidate | **Priority:** Low | **Product Area:** Auxiliary Modules
- **Governing Source:** `ROADMAP.md` Phase 14 ("Tax-aware features where appropriate")
- **Dependencies:** DS-PRT (Portfolio, Planned, Phase 4)
- **Rationale:** Named directionally in `ROADMAP.md` Phase 14 without detail; budgeting itself is not named anywhere in the Codex and is a genuinely new candidate.
- **Promotion Criteria:** Tax-feature scope narrowed to informational tax-lot reporting (not tax advice) per legal review; budgeting evaluated separately for product fit; dedicated DS-002 requirement authored.
- **Risks:** Tax guidance can constitute regulated financial/tax advice depending on jurisdiction and framing; requires careful scoping as informational only, consistent with DS-001 §21's "not a substitute for user judgment" non-goal.
- **Open Questions:** Whether budgeting belongs in DarkSage's product identity at all (DS-001 §4 defines DarkSage as a trading intelligence platform, not a personal-finance app).
- **Related Volumes/ADRs:** DS-001 §4, §21.
- **Review Gates:** Legal/Compliance, Owner Approval.
- **Notes:** None.

#### DS-BL-026 — Premium/Optional Modules

- **Summary:** A business-model concept for gating certain advanced or costly capabilities (e.g., cloud-AI-heavy features, premium data feeds) behind an optional paid tier.
- **Status:** Candidate | **Priority:** Low | **Product Area:** Business/Monetization
- **Governing Source:** None — net-new candidate, no current Codex grounding
- **Dependencies:** None
- **Rationale:** A plausible monetization direction for cost-intensive optional capability; not yet evaluated against `AGENTS.md`'s Cheap-First Architecture principle or DS-001's non-goals.
- **Promotion Criteria:** Owner decision on monetization model; confirmation that gating never restricts a Committed/MVP capability (DS-001 §18's rejection of artificial capability limits) or a safety-relevant control; dedicated requirement authored.
- **Risks:** Gating a safety- or risk-relevant capability behind payment would conflict with DS-001 §8.4 (Visible Risk) and DS-PRD-006 if mishandled — any premium tier must exclude safety-critical functionality.
- **Open Questions:** Entire business model undecided.
- **Related Volumes/ADRs:** DS-001 §18, §8.4.
- **Review Gates:** Owner Approval, Legal/Compliance.
- **Notes:** None.

### 6.8 Social and Engagement

#### DS-BL-012 — Social, Friends, and Competition Features

- **Summary:** User-to-user social features — following other users, shared watchlists, friendly competition on paper-trading or strategy performance.
- **Status:** Candidate | **Priority:** Low | **Product Area:** Social & Engagement
- **Governing Source:** None — net-new candidate, no current Codex grounding
- **Dependencies:** DS-USR-006 (Local User Profile Identity, Planned) — would need to extend beyond single-local-profile scope
- **Rationale:** Commonly requested in trading-adjacent products; not yet evaluated against DS-001's privacy-by-design and local-first principles, which a social feature set inherently tensions with.
- **Promotion Criteria:** Privacy model defined (what is shared, opt-in only, per DS-SEC-002/003); explicit owner approval given the shift away from single-user local-first design; dedicated requirement authored.
- **Risks:** Directly tensions with DS-001 §14's local-first/privacy-by-design preference; risks encouraging trade-frequency-driven engagement, which DS-001 §9 explicitly says the platform should not optimize for.
- **Open Questions:** Whether any social feature is consistent with DS-001's "not optimize for engagement, trade frequency" product philosophy.
- **Related Volumes/ADRs:** DS-001 §9, §14.
- **Review Gates:** Owner Approval, Legal/Compliance, Security.
- **Notes:** None.

#### DS-BL-013 — Gamification, Ranks, and Missions

- **Summary:** Achievement/rank/mission-style engagement mechanics layered on product usage or paper-trading performance.
- **Status:** Candidate | **Priority:** Low | **Product Area:** Social & Engagement
- **Governing Source:** None — net-new candidate, no current Codex grounding
- **Dependencies:** DS-BL-012 if social/competitive elements are included
- **Rationale:** A common engagement pattern in consumer apps; directly tensions with DS-001's explicit rejection of engagement-optimization as a design goal.
- **Promotion Criteria:** Owner review confirming any gamification mechanic does not incentivize excessive trading, overconfidence, or risk-taking (DS-001 §9, §13); dedicated requirement authored only if that review passes. Any mechanic that does proceed to a dedicated requirement must additionally be **non-manipulative** (no mechanic designed to exploit cognitive bias to drive trading activity), **user-controlled** (opt-in, and fully disable-able at any time without losing access to any underlying analytical capability, per Presentation Independence/ADR-004), **optional** (never a default-on experience, never required to access core product functionality), **transparent** (the mechanic's existence, purpose, and any performance-linked framing disclosed plainly, never disguised as neutral product chrome), and **subordinate to product safety and user welfare** (yields immediately to any Risk Engine, Sage-advisory, or explainability obligation it might otherwise compete with for attention). These five properties are necessary conditions for any future gamification requirement, not a promotion decision made now — this item's Status remains Candidate and this repair neither approves nor rejects it.
- **Risks:** High — gamifying trading-adjacent behavior can directly encourage the "activity over understanding" pattern DS-001 §5 identifies as a problem DarkSage exists to reduce, not reinforce.
- **Open Questions:** Whether this concept is compatible with DS-001 at all; leans toward Rejected pending owner review.
- **Related Volumes/ADRs:** DS-001 §5, §9.
- **Review Gates:** Owner Approval.
- **Notes:** Flagged as high-risk against core product philosophy; recommend owner review before any further development of this item.

### 6.9 Out of Scope

#### DS-BL-014 — Military-Path / Branch-Specific Fitness Crossover Concepts

- **Summary:** A previously-recorded idea concerning military-branch-specific fitness content/crossover, unrelated to trading intelligence.
- **Status:** Rejected / Not Pursuing | **Priority:** Low | **Product Area:** Out of Scope
- **Governing Source:** None
- **Dependencies:** None
- **Rationale:** DS-001 §4 (Product Definition) establishes DarkSage as a trading intelligence and decision-support platform; a fitness/military-branch crossover concept has no identifiable connection to that product definition and is out of scope.
- **Promotion Criteria:** Not applicable — rejected.
- **Risks:** Not applicable.
- **Open Questions:** None.
- **Related Volumes/ADRs:** DS-001 §4.
- **Review Gates:** None.
- **Notes:** Retained here per DS-BLG-002's rule that Rejected items are recorded, not silently omitted, so the disposition and reasoning are traceable.

### 6.10 Mobile

#### DS-BL-015 — Mobile/iPhone Capability Expansion Beyond Phase 9

- **Summary:** Mobile capability beyond `ROADMAP.md` Phase 9's baseline (dashboard, signals, watchlists, charts, portfolio monitoring, Sage chat, push notifications, Auto-Trader status, Emergency Stop, trade approvals) — e.g., deeper charting parity, offline analysis, Android support.
- **Status:** Approved Future | **Priority:** Medium | **Product Area:** Mobile
- **Governing Source:** `ROADMAP.md` Phase 9 ("Android-ready architecture"); DS-ARC-003 (Planned)
- **Dependencies:** DS-ARC-003/DS-MOB Phase-9 baseline implemented first
- **Rationale:** Phase 9 already anticipates Android-ready architecture as future direction; specific expansion beyond the named Phase-9 feature list is not yet its own requirement.
- **Promotion Criteria:** Specific capability authored as its own DS-MOB requirement once the Phase-9 baseline exists.
- **Risks:** None beyond standard mobile-security review (DS-SCA-017).
- **Open Questions:** Android timeline undecided.
- **Related Volumes/ADRs:** DS-002 (DS-MOB), DS-004 (DS-ARC-003/024); DS-014 DS-IDEA-016 (Future Multi-Device Coordination — related but distinct scope: DS-IDEA-016 is cross-device handoff/coordination once both clients exist, not general mobile capability expansion; not a counterpart of this item).
- **Review Gates:** Architecture.
- **Notes:** None.

### 6.11 Workspace and UX

#### DS-BL-016 — Multi-Monitor and Workspace Growth

- **Summary:** Multi-monitor/detachable-window workspace support and further Workspace Studio growth beyond DS-WKS-001–005.
- **Status:** Deferred | **Priority:** Low | **Product Area:** Workspace & UX
- **Governing Source:** DS-WKS-006 (Future/Exploratory); DS-UX-006 (Future/Exploratory)
- **Dependencies:** DS-WKS-003/004/005 (Planned) implemented first
- **Rationale:** Already tracked as Future/Exploratory at the DS-002/DS-007 level (DS-WKS-006, DS-UX-006); this backlog entry exists to give it a single cross-referenceable tracking point rather than being restated.
- **Promotion Criteria:** Owner decision on nearer-term commitment (DS-002 Appendix A Open Question #3) before promotion to Planned.
- **Risks:** None significant; primarily an implementation-complexity/priority question.
- **Open Questions:** Same as DS-002 Appendix A Open Question #3 (unchanged, not re-litigated here).
- **Related Volumes/ADRs:** DS-002 (DS-WKS-006), DS-007 (DS-UX-006); DS-014 DS-IDEA-015 (Advanced Workspace Studio Concepts — related but distinct scope: DS-IDEA-015 covers workspace-suggestion/template concepts beyond current DS-WKS/DS-UX scope generally, not specifically multi-monitor/detachable-window support; not a counterpart of this item).
- **Review Gates:** None beyond normal review.
- **Notes:** None.

### 6.12 Sage and AI Research Track

#### DS-BL-017 — Sage Memory (Persistent, Cross-Session)

- **Summary:** Cross-session, personalized memory for Sage, allowing it to recall prior conversations/context across sessions rather than only within a session.
- **Status:** Research Needed | **Priority:** Medium | **Product Area:** Sage & AI
- **Governing Source:** DS-001 §22 (Future Aspiration); DS-003 §4 ("Persistent Sage Memory" term, explicitly "not part of the current Committed/MVP or Planned scope")
- **Dependencies:** DS-003's Phase-6 session-scoped memory (Planned) implemented first
- **Rationale:** Already named as a future aspiration at the DS-001/DS-003 level; the technical persistence architecture and privacy model are not yet designed.
- **Promotion Criteria:** Privacy/data-retention model defined (what is stored, for how long, user control per DS-SEC); technical architecture evaluated; dedicated DS-003/DS-004 requirement authored.
- **Risks:** Persistent personal data storage increases the DS-008 threat-model surface (new protected asset); must integrate with DS-SCA-023's asset catalog if promoted.
- **Open Questions:** Local-only vs. any cloud-assisted storage; retention duration.
- **Related Volumes/ADRs:** DS-001 §22, DS-003.
- **Review Gates:** Architecture, Security.
- **Notes:** None.

#### DS-BL-018 — Specialized Local Financial Models

- **Summary:** Purpose-built local models for financial/market analysis, beyond the general-purpose local/cloud AI provider abstraction `ROADMAP.md` Phase 6 already scopes.
- **Status:** Research Needed | **Priority:** Medium | **Product Area:** Sage & AI
- **Governing Source:** DS-RM-009 (DS-011, Committed governance boundary — explicitly defers this to the backlog/idea-parking track rather than committing it)
- **Dependencies:** DS-ARC-014 (Local-First AI, Planned) implemented first
- **Rationale:** DS-RM-009 explicitly names this as Future/Exploratory research, not part of `ROADMAP.md` Phase 6's committed general-purpose provider scope.
- **Promotion Criteria:** Model benchmarking against general-purpose providers on DarkSage-relevant tasks; compute/deployment cost evaluated; dedicated requirement authored only if benchmarking shows meaningful advantage. Where a specific third-party base model or weight set is a candidate, all nine of DS-IDG-004's mandatory gates (licensing, independent benchmarking, compute requirements, privacy, security, model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, operational feasibility) apply in full before promotion.
- **Risks:** Specialized model training/maintenance cost; risk of the model becoming a de facto authoritative source for something that should remain deterministic (DS-PRD-004 boundary must be preserved regardless of model quality); a third-party base model/weight set carries untrusted-artifact and supply-chain risk until verified per DS-IDG-004.
- **Open Questions:** Which specific analytical tasks would benefit from specialization.
- **Related Volumes/ADRs:** DS-011 (DS-RM-009), DS-014 (DS-IDEA-001, DS-IDEA-004, DS-IDEA-019, DS-IDEA-020 — cross-referenced per DS-BLG-006), DS-008.
- **Review Gates:** Model Benchmarking, Cost Evaluation, Architecture, Security.
- **Notes:** Cross-references DS-IDEA-001, DS-IDEA-004, DS-IDEA-019, DS-IDEA-020. Any specific third-party base model candidate is subject to DS-IDG-004's full nine-gate review.

#### DS-BL-019 — Market-Foundation-Model Research Track

- **Summary:** Research track evaluating foundation-model approaches (large pretrained models specialized for market/time-series data) as a potential future component of DarkSage's analytical stack.
- **Status:** Research Needed | **Priority:** Low | **Product Area:** Sage & AI
- **Governing Source:** DS-RM-009 (DS-011, Committed governance boundary)
- **Dependencies:** DS-BL-018
- **Rationale:** An emerging research area referenced in prior product discussion; not yet mature enough for a productization decision.
- **Promotion Criteria:** Research findings (DS-014) mature into a specific, benchmarked proposal before any DS-013 status change beyond Research Needed.
- **Risks:** High uncertainty; foundation-model claims in the financial domain are frequently unproven at production scale — DS-QA-011's non-substitution rule (model evaluation never replaces deterministic verification) applies to any output from this track without exception.
- **Open Questions:** Entire research question — see DS-014.
- **Related Volumes/ADRs:** DS-009 (DS-QA-011), DS-014 (DS-IDEA-001, DS-IDEA-002, DS-IDEA-003).
- **Review Gates:** Model Benchmarking, Architecture.
- **Notes:** Cross-references DS-IDEA-001, DS-IDEA-002, DS-IDEA-003.

#### DS-BL-020 — Kronos Evaluation

- **Summary:** Evaluation of Kronos (an external market-tokenization/time-series research reference) as one possible input to the market-foundation-model research track.
- **Status:** Research Needed | **Priority:** Low | **Product Area:** Sage & AI
- **Governing Source:** None — external research reference, not a Codex-approved direction
- **Dependencies:** DS-BL-019
- **Rationale:** Named specifically as a research reference worth evaluating; explicitly not a committed dependency or an assumed-superior model.
- **Promotion Criteria:** All nine of DS-IDG-004's mandatory gates satisfied and recorded — licensing, independent benchmarking (against alternatives and DarkSage's own deterministic baselines), compute requirements, privacy, security (per DS-008), model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, and operational feasibility. No promotion beyond Research Needed without all nine.
- **Risks:** Unvalidated third-party model risk; licensing terms unknown until reviewed; performance claims unverified until independently benchmarked; model weights are an untrusted artifact until integrity/provenance is verified; training-data privacy and supply-chain provenance not yet assessed.
- **Open Questions:** All nine DS-IDG-004 gates unresolved — see DS-IDEA-002.
- **Related Volumes/ADRs:** DS-014 (DS-IDEA-002), DS-008.
- **Review Gates:** Model Benchmarking, Legal/Compliance (licensing), Cost Evaluation, Security.
- **Notes:** Cross-references DS-IDEA-002. Per DS-IDG-004, Kronos is treated strictly as an architectural/research reference throughout this Codex — never a committed dependency, never assumed superior to alternatives without benchmarking, and subject to the full nine-gate review (licensing, independent benchmarking, compute requirements, privacy, security, model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, operational feasibility) before any promotion.

#### DS-BL-021 — Model Fine-Tuning and Distillation Pipeline

- **Summary:** Infrastructure for fine-tuning or distilling smaller local models from larger reference models for DarkSage-specific tasks.
- **Status:** Research Needed | **Priority:** Low | **Product Area:** Sage & AI
- **Governing Source:** DS-RM-009 (DS-011, Committed governance boundary)
- **Dependencies:** DS-BL-018/019
- **Rationale:** A plausible technical path to local specialized models without the cost of training from scratch; not yet evaluated.
- **Promotion Criteria:** All nine of DS-IDG-004's mandatory gates (licensing, independent benchmarking, compute requirements, privacy, security, model-supply-chain risk, untrusted-artifact/weight handling, integration-boundary risk, operational feasibility) satisfied and recorded for each candidate base/reference model; dedicated requirement authored only after a specific target model/task is identified and all gates pass.
- **Risks:** Base-model licensing may restrict fine-tuning/redistribution; base-model weights are an untrusted artifact until integrity/provenance is verified; requires careful review before any pipeline is built.
- **Open Questions:** Target base model(s) not yet identified — see DS-IDEA-020.
- **Related Volumes/ADRs:** DS-014 (DS-IDEA-020), DS-008.
- **Review Gates:** Model Benchmarking, Legal/Compliance, Cost Evaluation, Security.
- **Notes:** Cross-references DS-IDEA-020. Any specific target base model is a third-party model candidate under DS-IDG-004 and subject to its full nine-gate review before promotion.

#### DS-BL-022 — Additional Explainability and Evidence-Fusion Systems

- **Summary:** Explainability presentation and multi-source evidence-fusion capability beyond DS-AI-003/DS-SGE-008/013's Planned baseline — e.g., combining structured (deterministic) and unstructured (news/filing) evidence into one coherent explanation.
- **Status:** Candidate | **Priority:** Medium | **Product Area:** Sage & AI
- **Governing Source:** DS-PRD-002 (Committed, evidence provenance); DS-AI-003 (Planned)
- **Dependencies:** DS-AI-003/DS-SGE-013 (Planned, Phase 6) implemented first
- **Rationale:** DS-PRD-002/DS-AI-003 already establish the evidence-provenance obligation; a dedicated fusion architecture for combining multiple evidence types is not yet defined.
- **Promotion Criteria:** Fusion architecture designed, preserving DS-PRD-002's per-source provenance/timestamp requirement for each fused input; dedicated DS-003/DS-004 requirement authored.
- **Risks:** Poorly designed fusion could obscure which claims trace to which evidence, violating DS-PRD-002's traceability requirement.
- **Open Questions:** Fusion architecture — see DS-IDEA-007, DS-IDEA-021, DS-IDEA-022, DS-IDEA-024.
- **Related Volumes/ADRs:** DS-002 (DS-PRD-002, DS-AI-003), DS-014 (DS-IDEA-007, DS-IDEA-021, DS-IDEA-022, DS-IDEA-024).
- **Review Gates:** Architecture.
- **Notes:** Cross-references DS-IDEA-007, DS-IDEA-021, DS-IDEA-022, DS-IDEA-024.

### 6.13 Portfolio

#### DS-BL-023 — Portfolio Construction Enhancements

- **Summary:** Enhancements beyond DS-PRT-001–004 — e.g., factor-based construction, tax-loss-harvesting-aware rebalancing, goal-probability modeling refinements.
- **Status:** Planned | **Priority:** Medium | **Product Area:** Portfolio
- **Governing Source:** DS-PRT-001–004 (all Planned); `ROADMAP.md` Phase 4 ("Factor exposure," "Goal probability")
- **Dependencies:** DS-PRT-001–004 (Phase 4 baseline) implemented first
- **Rationale:** `ROADMAP.md` Phase 4 already names factor exposure and goal probability directionally; specific enhancement requirements are not yet authored.
- **Promotion Criteria:** Specific enhancement authored as its own DS-PRT requirement once the Phase-4 baseline exists.
- **Risks:** None beyond standard deterministic-calculation discipline (DS-PRD-004 applies to any new portfolio metric).
- **Open Questions:** None beyond normal Phase-4 authoring scope.
- **Related Volumes/ADRs:** DS-002 (DS-PRT).
- **Review Gates:** None beyond normal review.
- **Notes:** None.

### 6.14 Alerts and Automation

#### DS-BL-024 — Alerts and Automation Enhancements

- **Summary:** Alert/automation capability beyond DS-ALT-001–003 — e.g., multi-condition composite alerts, automation recipes that trigger a notification chain.
- **Status:** Planned | **Priority:** Medium | **Product Area:** Alerts & Automation
- **Governing Source:** DS-ALT-001–003 (all Planned)
- **Dependencies:** DS-ALT-001/002 (Planned) implemented first
- **Rationale:** DS-ALT already has a Planned baseline; further composite/automation capability is not yet its own requirement.
- **Promotion Criteria:** Specific capability authored as its own DS-ALT requirement, explicitly preserving DS-PRD-007's notification-only boundary — no automation enhancement may create an execution path (DS-API-ALT-001's acceptance criteria already fix this boundary).
- **Risks:** Any automation "recipe" concept must be carefully bounded to avoid resembling autonomous trade execution, which remains out of scope absent separate governance (DS-PRD-007).
- **Open Questions:** Specific composite-condition scope not yet defined.
- **Related Volumes/ADRs:** DS-002 (DS-ALT, DS-PRD-007), DS-006 (DS-API-ALT-001).
- **Review Gates:** Architecture.
- **Notes:** None.

### 6.15 Performance and Interaction Feedback

#### DS-BL-027 — Responsive Loading and Interaction Feedback

- **Summary:** Improve perceived performance, interaction clarity, and user understanding through skeleton loaders, controlled caching, optimistic rendering for safe reversible actions, and contextual tooltips.
- **Status:** Approved Future | **Priority:** Medium | **Product Area:** Performance & Interaction Feedback
- **Governing Source:** Founder-approved backlog addition (this repair pass); DS-UX-016 (Committed, Interface State Lifecycle — this item builds on that Committed baseline without altering it); DS-UX-022 (Planned, Accessible Interface State Announcements); DS-PRD-003 (Committed, Presentation Independence)
- **Dependencies:** DS-UX-016 (Committed core lifecycle) as the foundation this item extends; DS-UX-022 for accessibility-announcement integration
- **Rationale:** DS-UX-016 already establishes the Committed/MVP interface-state lifecycle (Loading/Ready/Refreshing/Degraded-Partial/Error/Retry-Recovery). This item captures the specific UX techniques — skeleton loaders, caching, optimistic rendering, contextual tooltips — that would implement and enrich that lifecycle across concrete surfaces, without altering DS-UX-016's own Committed acceptance criteria.
- **Required Capabilities:**
  - Skeleton loaders for dashboards, scanner results, charts, portfolio views, research results, and Sage interactions where appropriate.
  - Client and server caching with explicit freshness, provenance where relevant, invalidation, expiration, and stale-state behavior, consistent with DS-UX-012's data-state/provenance labeling and DS-API-COR-002's response envelope.
  - Optimistic rendering restricted to low-risk, reversible actions only: watchlist changes, layout preferences, filters, notes, and other clearly non-authoritative interface preferences.
  - Automatic rollback and a visible error state when an optimistic update fails.
  - Contextual tooltips for indicators, scores, abbreviations, controls, risk states, and unfamiliar financial terminology (building on DS-EDU-001's contextual terminology reference where applicable).
  - Keyboard, focus, screen-reader, and accessible-description support where applicable (DS-UX-017/DS-UX-022).
  - Loading, stale, offline, empty, partial, failed, and retry states remain distinguishable at all times (extends DS-UX-016).
  - Presentation behavior must never change underlying capability state or authoritative backend state (DS-PRD-003/DS-UX-001 — Presentation Independence applies without exception).
- **Hard Safety Boundary (non-negotiable):** Optimistic rendering is prohibited for: trades or orders; broker actions; risk-limit changes; permission changes; Emergency Stop or Emergency Flatten actions; credentials; authentication state; strategy promotion or activation; authoritative portfolio/account state; and any other irreversible, security-sensitive, financially material, or safety-critical action. For every prohibited action, the interface waits for authoritative backend confirmation and clearly shows pending, accepted, rejected, failed, or timed-out state. This restates — and never weakens — DS-EXE-001/DS-API-EXE-001's `TradeValidationPipeline` boundary, DS-SCA-012's order-authorization-trail requirement, and DS-PRD-005's user-decision-authority principle at the UI-optimism layer specifically.
- **Promotion Criteria:** A dedicated DS-007 (DS-UX) requirement (or set of requirements) authored, explicitly extending DS-UX-016 rather than duplicating it; the Hard Safety Boundary list above verified against DS-EXE-001/DS-API-EXE-001/DS-SCA-012 with no exception; a dedicated DS-009 (DS-QA) test category added for optimistic-rendering rollback and prohibited-action-boundary adversarial testing.
- **Risks:** An improperly scoped optimistic-rendering implementation could blur the line between a client-side preference change and an authoritative backend action if the Hard Safety Boundary is enforced only in UI copy and not in code — this item exists specifically to fix that boundary now, before implementation. Caching with unclear staleness could violate DS-PRD-008 if not integrated with DS-UX-012's existing state-labeling pattern.
- **Open Questions:** Exact set of surfaces requiring skeleton loaders beyond the six named; specific cache invalidation policy per data type.
- **Related Volumes/ADRs:** DS-007 (DS-UX-001/012/016/017/022), DS-002 (DS-PRD-003/005/008), DS-006 (DS-API-COR-002), DS-008 (DS-SCA-012), DS-002 (DS-EXE-001), DS-006 (DS-API-EXE-001), ADR-004.
- **Review Gates:** Architecture.
- **Notes:** Founder-approved addition (this repair pass). Placed in DS-013, not DS-014 — inclusion here is a tracked product capability, not an implementation commitment (DS-BLG-001). The Hard Safety Boundary is fixed now as a non-negotiable constraint on any future implementation, mirroring the governance-boundary-now/implementation-later pattern DS-API-EXE-001 already establishes elsewhere in this Codex.

## 7. Non-Goals

DS-013 does not: promote any listed item to Committed, Planned, or otherwise approved status by virtue of inclusion (DS-BLG-001); redesign or restate any DS-002 through DS-012 requirement; invent calendar dates or delivery commitments; or duplicate DS-014's research-stage idea content as a second, competing description (DS-BLG-006 — cross-reference instead).

## 8. Dependencies

- [DS-001](../Volume-01-Foundation/DS-001-Executive-Vision.md), [DS-002](../Volume-02-Product/DS-002-SRS.md), [DS-008](../Volume-08-Security/DS-008-Security-Architecture.md), [DS-009](../Volume-09-Testing/DS-009-Testing-and-QA.md), [DS-011](../Volume-11-Roadmap/DS-011-Development-Roadmap.md), [DS-012](../Volume-12-ADRs/DS-012-Architecture-Decision-Records.md)
- `ROADMAP.md`, `PROJECT_SPEC.md`, `AGENTS.md`, `SECURITY_RULES.md`
- [DS-014](../Volume-14-Ideas/DS-014-Idea-Parking-Lot.md) (this batch, cross-referenced items)

## 9. Risks and Constraints

- **Classification discipline:** no backlog item carries a Release Classification; every item explicitly states its Promotion Criteria rather than implying current approval.
- **Product-philosophy tension flagged, not resolved:** DS-BL-012/013 (social/gamification) are recorded with an explicit risk note that they may conflict with DS-001's anti-engagement-optimization philosophy; this document does not resolve that tension — it surfaces it for owner review, consistent with DS-BLG-004's Owner Approval flag.
- **AI/model-research items deliberately conservative:** DS-BL-018 through 022 all carry Research Needed status and explicit Model Benchmarking gates, preventing any premature productization claim about unproven model capability, consistent with DS-QA-011's non-substitution rule.

## 10. Verification Approach

Document-level verification (unique-ID check across `DS-BLG-NNN`/`DS-BL-NNN`, cross-reference consistency against DS-001/DS-002/DS-008/DS-009/DS-011/DS-012, no item carrying an implied Release Classification, DS-014 cross-references valid) recorded in `.ai-workflow/HANDOFF.md`.

## 11. References

- `ROADMAP.md`, `PROJECT_SPEC.md`, `AGENTS.md`, `SECURITY_RULES.md`
- `docs/codex/Volume-02-Product/DS-002-SRS.md` and `requirements/*.md`
- `docs/codex/Volume-11-Roadmap/DS-011-Development-Roadmap.md`
- `docs/codex/Volume-12-ADRs/DS-012-Architecture-Decision-Records.md`
- `docs/codex/Volume-14-Ideas/DS-014-Idea-Parking-Lot.md`

## Appendix A — Open Questions

1. **Product-philosophy fit for social/gamification features (DS-BL-012/013)** — recorded as a genuine open question for owner review, not resolved here; leans toward Rejected given DS-001's explicit anti-engagement-optimization stance.
2. **Tax/budgeting product-identity fit (DS-BL-011)** — whether budgeting belongs in DarkSage's scope at all is unresolved.
3. **Futures/crypto asset-class fit (DS-BL-008/009)** — entirely unevaluated; recorded for future research only.
4. **Governance-confirmation carryover** — the standing `BLOCKERS.md` items (`ROADMAP.md` phase boundaries as Codex release-scope authority; multi-monitor commitment level, DS-BL-016) apply identically here and are not re-litigated.
