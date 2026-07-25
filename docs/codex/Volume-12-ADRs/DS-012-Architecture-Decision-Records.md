# DS-012 — Architecture Decision Records

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-012 |
| Title | Architecture Decision Records |
| Version | 0.2.3 |
| Status | Draft |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-24 |
| Last Updated | 2026-07-25 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| 0.1.0 | 2026-07-24 | TheSinnerMan | First controlled draft, authored as part of the Batch 2 grouped pass (DS-010/DS-011/DS-012). Establishes the ADR governance layer (lifecycle, creation/approval rules, metadata, decision-history, superseding/deprecating rules, conflict-resolution hierarchy) and indexes the four existing, approved ADRs (ADR-001 through ADR-004) without restating or weakening their decisions. |
| 0.2.0 | 2026-07-24 | TheSinnerMan | Targeted repair for independent-audit findings DS-012-H1/H2. **H1:** `DS-ADR-003`/`DS-ADR-009` no longer cite `.ai-workflow/KEEPER_AUTHORITY.md` as Governing Source; ADR approval authority is now grounded in DS-012 itself (Owner authority, or explicitly delegated approval within documented scope, recorded as reproducible evidence in the ADR's own Decision History or an equivalent committed record) — local workflow files may facilitate an approval but never constitute its authority. Does not broaden delegated authority beyond its existing local operational boundary. **H2:** `DS-ADR-010` rewritten into one explicit six-tier conflict-resolution hierarchy (root mandatory safety governance → approved owner decisions → Approved ADRs → Approved Codex volumes → implementation documentation → local workflow files), stating explicitly that no ADR may weaken or override `SECURITY_RULES.md`, `TRADING_RULES.md`, Risk Engine authority, deterministic financial truth, or mandatory pipeline safeguards, that same-tier/ambiguous-tier conflicts stop work for Owner/governance resolution, and that superseding an ADR never supersedes root safety governance. |
| 0.2.1 | 2026-07-24 | TheSinnerMan | Consolidated cleanup pass: ADR-001 through ADR-004's previously template-minimal Context, Consequences, Alternatives Considered, and Related Requirements sections were populated (each ADR bumped 1.0.0 → 1.1.0) in this same pass, closing the retrofit item DS-ADR-003's Acceptance Criteria and Appendix A Open Question #1 recorded as deferred. §9 Index table updated to show Version 1.1.0 for all four ADRs; Appendix A Open Question #1 updated to reflect completion rather than deferral. **Correction (see 0.2.2):** this entry's claim that §13's retrofit note was also updated was inaccurate — that bullet was missed in this pass and remained stale until 0.2.2. |
| 0.2.2 | 2026-07-25 | TheSinnerMan | Suite-audit follow-up: corrected the one remaining stale statement from 0.2.1 — §13 Risks and Constraints still read "Existing ADRs are template-minimal... not fixed in this batch," contradicting the retrofit 0.2.1 actually performed. Reworded to state the retrofit is complete (ADR-001–004 all Version 1.1.0, grounded in DS-001/002/003/004/007/009, no Decision/Status/authority change), retaining the entry for revision-history traceability rather than deleting it. No ADR content, DS-012 governance authority, or index data changed beyond this wording correction. |
| 0.2.3 | 2026-07-25 | TheSinnerMan | Final mechanical repair: removed the two remaining stale retrofit statements missed by 0.2.1/0.2.2. `DS-ADR-004`'s Description referred to Context/Consequences/Alternatives Considered/Related Requirements' "current absence" in ADR-001–004; reworded to state they are now populated (retrofitted, each ADR at Version 1.1.0). §11 Non-Goals said the retrofit was "not performed here since it is outside this batch's authorized files"; reworded to state the retrofit has been completed directly in the four ADR files, with DS-012's Non-Goal being that it does not itself duplicate that retrofitted content (only indexes it, §9). No ADR Decision, Status, approval authority, or DS-012 governance content changed — wording-only correction. |

## 1. Purpose

DS-012 governs DarkSage's Architecture Decision Record (ADR) system: what an ADR is, when one is required, how it is created and approved, how it relates to the rest of the Codex, and how the existing ADRs are indexed. DS-012 does not decide architecture itself and does not restate or weaken any existing approved ADR's decision — `docs/codex/Volume-12-ADRs/ADR-NNN-*.md` files remain the sole authoritative record of their own decisions. DS-012 governs and indexes them; it is not a competing or parallel authority.

## 2. Scope

This document governs: ADR purpose and authority; the ADR lifecycle; creation and approval rules; metadata requirements; decision-history rules; superseding/deprecating rules; the relationship between ADRs and DS-001 through DS-011; when an ADR is required and when it is not; the conflict-resolution hierarchy; traceability expectations; implementation/review responsibilities; an index of ADR-001 through ADR-004; and the process for adding future ADRs.

DS-012 does not govern: the content of any individual architectural decision (the `ADR-NNN` files themselves are authoritative); general technical architecture not yet the subject of a durable decision (DS-004); or development process unrelated to decision governance (DS-010).

## 3. Audience

Contributors proposing or implementing architectural decisions, independent auditors, and future Codex authors.

## 4. Definitions

See DS-001 §24 and DS-002 §4. Additional terms:

| Term | Meaning |
|---|---|
| Architecture Decision Record (ADR) | A controlled document (`ADR-NNN`) recording one material, durable architectural or product-governing decision, its status, and its history |
| Supersede | Replace a prior ADR's decision with a new one; the prior ADR's Status becomes Superseded and it is never deleted |
| Deprecate | Mark a prior ADR's decision no longer applicable without a direct replacement; the prior ADR's Status becomes Deprecated |
| Durable decision | A decision intended to remain stable across product versions, distinct from a routine or easily reversible implementation choice |

## 5. ADR Purpose and Authority

### DS-ADR-001 — ADR Purpose and Authority

**Release Classification:** Committed / MVP | **Governing Source:** DS-001 §11 (Constitution #12, Committed); `docs/templates/markdown/ADR.md`

**Description:** An ADR records one material, durable architectural or product-governing decision — the kind DS-001 Constitution #12 ("major features, requirements, and material decisions enter the DarkSage Codex before implementation") requires enter the Codex. An Approved ADR sits, alongside DS-001, at the top of this Codex's internal decision hierarchy (DS-ADR-010): DS-002 through DS-011 requirements may cite and depend on an ADR, but none may override, contradict, or silently reinterpret one. DS-012 governs the ADR system; it does not itself decide architecture or duplicate an ADR's content as a second authority.

**Acceptance Criteria:**
- No DS-002 through DS-011 requirement contradicts an Approved ADR's Decision.
- No DS-012 content restates an existing ADR's Decision text as if DS-012 were an independent source for it — DS-012 cites the ADR by ID (§9).

**Testing:** Cross-volume contradiction check between every Approved ADR and DS-002 through DS-011, performed on every ADR or affected-volume revision.

## 6. ADR Lifecycle and Metadata

### DS-ADR-002 — ADR Lifecycle

**Release Classification:** Committed / MVP | **Governing Source:** `docs/templates/markdown/ADR.md` (Committed, existing template); DS-002 §5's Status lifecycle convention

**Description:** An ADR's Status progresses Draft → Under Review → Approved → Superseded/Deprecated, matching the lifecycle every controlled Codex document already states. Only an Approved ADR binds DS-002 through DS-011 per DS-ADR-001; a Draft or Under Review ADR records a proposed decision that does not yet bind anything.

**Acceptance Criteria:** Matches the existing ADR template's stated lifecycle exactly; no ADR skips a stage without a recorded reason (e.g., an emergency decision fast-tracked with explicit Keeper/Owner sign-off).

**Testing:** Status-field consistency check against the Decision History table (DS-ADR-005) on every ADR revision.

### DS-ADR-003 — Creation and Approval Rules

**Release Classification:** Committed / MVP | **Governing Source:** DS-012 (this document, normative); DS-001 §11 (Constitution #12)

**Description:** An ADR may be proposed (Draft) by any contributor or agent identifying a material, durable decision per DS-ADR-008. Approval to Approved status requires the repository Owner's authority, or an explicitly delegated approver acting strictly within documented scope. Delegated approval is recognized only when: (a) the delegation was explicitly granted by the Owner; (b) the specific approval falls within that delegation's documented scope; (c) the approval is recorded as reproducible evidence in the ADR's own Decision History (DS-ADR-005) or an equivalent committed commit/review record — never solely in a local, non-committed file; and (d) the decision is not a destructive or high-risk action outside the delegation's scope. An ADR proposing to supersede or deprecate an existing Approved ADR follows the same approval requirement as creating a new one. A local session-coordination file may facilitate how a specific delegated approval was reached in practice — recording its scope and boundaries is a local operational matter — but it never itself constitutes durable approval authority; the ADR's own Decision History entry is what makes an approval durable and reproducible from repository records. This requirement does not create, broaden, or otherwise define delegated authority beyond what is already established as a local operational boundary — it states only the *public, reproducible-record* requirement any delegated approval must satisfy to bind an ADR.

**Acceptance Criteria:**
- No ADR reaches Approved status without a recorded approver (Owner, or an explicitly delegated approver within documented scope) evidenced in the ADR's own Decision History or an equivalent committed record.
- A major architecture change proposed via ADR that falls outside any documented delegation scope is never approved by a delegate alone — it requires the Owner.
- No ADR's approval is evidenced solely by a local, non-committed file; the Decision History entry (or equivalent committed record) is authoritative.

**Testing:** Approval-record audit against each ADR's own Decision History table and, where applicable, associated commit/review evidence.

### DS-ADR-004 — Metadata Requirements

**Release Classification:** Committed / MVP | **Governing Source:** `docs/templates/markdown/ADR.md` (Committed, existing template)

**Description:** Every ADR's Document Control table states, at minimum: Document ID (`ADR-NNN`), Title, Version, Status, Owner, Classification, Repository, Created, and Last Updated — matching the fields the four existing ADRs already carry. An ADR's body includes at minimum a Decision statement and a Decision History table; Context, Consequences, Alternatives Considered, and Related Requirements are present in the template and are now populated in ADR-001 through ADR-004 (retrofitted in the consolidated Codex cleanup pass, each bumped to Version 1.1.0). Their populated content is additive context grounded in already-approved material — it does not alter, and did not need to alter, those already-Approved decisions (DS-ADR-001 — DS-012 does not weaken them).

**Acceptance Criteria:**
- Every ADR's Document Control table matches `docs/templates/markdown/ADR.md`'s field set exactly.
- A new ADR (created after this document) includes a populated Context and Consequences section from creation, since the template's expectation is now explicit; ADR-001 through ADR-004 had their Context, Consequences, Alternatives Considered, and Related Requirements sections retrofitted in the consolidated Codex cleanup pass (each now Version 1.1.0), closing the gap this criterion originally flagged as non-blocking.

**Testing:** Metadata-field completeness check against the ADR template, performed on every ADR creation or revision.

### DS-ADR-005 — Decision History Rules

**Release Classification:** Committed / MVP | **Governing Source:** `docs/templates/markdown/ADR.md` (Committed, existing template)

**Description:** Every version change to an ADR is recorded as a new row in its Decision History table (Version, Date, Status, Owner, Summary) — an Approved decision's content is never silently edited without a recorded, versioned change. A correction to an ADR's wording that does not change its substantive Decision is a new patch version with a Decision History entry explaining the correction; a substantive change to the Decision itself is a new ADR that supersedes the prior one (DS-ADR-006), never an in-place rewrite of an Approved decision.

**Acceptance Criteria:**
- Every ADR's Version field matches its Decision History table's latest row.
- No Approved ADR's Decision text differs from its Decision History's most recent Approved-status entry without a corresponding new row.

**Testing:** Version/Decision-History consistency check on every ADR revision.

### DS-ADR-006 — Superseding and Deprecating Rules

**Release Classification:** Committed / MVP | **Governing Source:** `docs/templates/markdown/ADR.md` Status lifecycle (Committed)

**Description:** A new ADR that changes a prior Approved decision supersedes it by explicit ID reference in the new ADR's Context/Decision; the prior ADR's Status changes to Superseded, and its file content is never deleted — it remains the historical record. An ADR whose decision is no longer applicable with no direct replacement is marked Deprecated, with the reason recorded in its Decision History.

**Acceptance Criteria:**
- A Superseded ADR is never deleted; it remains readable and its Status field reflects Superseded.
- A superseding ADR explicitly names the ADR(s) it supersedes by ID.
- No two Approved ADRs make contradictory decisions on the same topic simultaneously — a contradiction is resolved by superseding one, not by leaving both Approved.

**Testing:** Cross-ADR contradiction check on every new ADR's approval.

## 7. Relationship to the Codex and Conflict Resolution

### DS-ADR-007 — Relationship to DS-001 through DS-011

**Release Classification:** Committed / MVP | **Governing Source:** DS-001 §23 (Governance Relationship, Committed); DS-ADR-001 (this document)

**Description:** Approved ADRs sit alongside DS-001 as durable-decision authority, per DS-001 §23's statement that "material architectural decisions should be captured through ADRs." A DS-002 through DS-011 requirement may cite an ADR as its Governing Source (as DS-PRD-004/DS-RSK-001/DS-PRD-003/DS-ARC-002 and many others already do for ADR-003/002/004/001 respectively) but never overrides one. If a lower-level proposal appears to conflict with an approved ADR, the conflict is documented and resolved through the controlled review process (DS-001 §23), not silently implemented around the ADR.

**Acceptance Criteria:** Matches DS-001 §23's acceptance behavior; every DS-002+ requirement citing an ADR as Governing Source is checked for contradiction on that ADR's own revision.

**Testing:** Cross-volume ADR-citation contradiction check (shared with DS-ADR-001's own test).

### DS-ADR-008 — When an ADR Is Required

**Release Classification:** Committed / MVP | **Governing Source:** DS-001 §11 (Constitution #12); the four existing ADRs' own topics as precedent

**Description:** A material, durable, cross-cutting decision with long-term product or architectural consequences requires an ADR before implementation — the same category ADR-001 through ADR-004 already occupy: platform direction (desktop-first), a safety boundary between two major subsystems (Sage/Risk Engine), a calculation-authority rule (deterministic financial calculations), and a UI/capability separation principle (Presentation Independence). A decision of comparable scope and durability (e.g., choosing the authentication token mechanism DS-006 Appendix A leaves open, or committing to a specific database-migration trigger) requires a new ADR when it is finally decided.

**Acceptance Criteria:**
- A decision matching this category's scope (platform-wide, safety-boundary, or calculation-authority in nature) is not merged as an ordinary requirement change without an accompanying ADR.
- Each of the open questions this Codex has recorded that meets this bar (e.g., DS-006 Appendix A #2 authentication mechanism) is expected to resolve via a future ADR, not a silent requirement edit.

**Testing:** Requirements-review checklist item: does this change's scope match ADR-001–004's category; if so, is an ADR present.

### DS-ADR-009 — When an ADR Is Not Required

**Release Classification:** Committed / MVP | **Governing Source:** DS-012 (this document, normative); DS-DEV-008/DS-DEV-010 (DS-010, Committed)

**Description:** A routine implementation decision within already-approved architecture, a reversible choice, or a decision already fully specified by an existing DS-002 through DS-011 requirement does not require a new ADR. Examples already present in this Codex: choosing a specific indicator library detail, a chart-widget default size, or a log-message format — none rise to ADR-001–004's scope and are governed by the relevant DS-00X requirement or DS-010's development standards instead. This mirrors DS-010's own minimum-practical-pass and non-blocking-suggestion-handling principles (DS-DEV-008/010): unnecessary process overhead is avoided on DS-012's own authority, not by appeal to any local operational file.

**Acceptance Criteria:** No routine, reversible, or already-specified decision is blocked pending an unnecessary ADR — consistent with DS-DEV-008's minimum-practical-pass philosophy.

**Testing:** Requirements-review checklist item (shared with DS-ADR-008's own check, applied in the negative direction).

### DS-ADR-010 — Conflict-Resolution Hierarchy

**Release Classification:** Committed / MVP | **Governing Source:** `SECURITY_RULES.md` "Core Security Rule"; `TRADING_RULES.md`; `AGENTS.md` Source-of-Truth priority order; DS-PRD-004/006 (both Committed)

**Description:** Repaired in the DS-012-H2 pass to state one clear hierarchy covering both root repository governance and the Codex — the prior version did not explicitly state that root mandatory safety governance outranks ADRs. From highest to lowest authority:

1. **Mandatory root security/trading governance and fixed-priority safety rules** — `SECURITY_RULES.md`, `TRADING_RULES.md`, the Risk Engine's independent authority (DS-RSK-001/DS-PRD-006), deterministic-financial-truth (DS-PRD-004/ADR-003), and the canonical `TradeValidationPipeline`'s mandatory safeguards (DS-EXE-001/DS-API-EXE-001) — aligned with `AGENTS.md`'s own fixed priority order (`SECURITY_RULES.md` > `TRADING_RULES.md` > `ARCHITECTURE.md` > `PROJECT_SPEC.md` > `ROADMAP.md` > `AGENTS.md`) for its two highest tiers.
2. **Approved owner decisions within those boundaries** — an explicit Owner decision that does not weaken tier 1.
3. **Approved ADRs** — ADR-001 through ADR-004 and any future Approved ADR.
4. **Approved Codex volumes/requirements** — DS-001 through DS-014 (as authored/approved); among these, a volume's own declared Scope (§2 of each) determines which is authoritative for a given topic (e.g., DS-006 for API contracts, DS-008 for security architecture) — a lower-numbered volume does not automatically outrank a higher-numbered one outside its own declared scope.
5. **Implementation documentation and code-level decisions** — design notes, code comments, and other sub-Codex documentation.
6. **Local workflow/convenience files** — `.ai-workflow/**` and equivalent local, non-committed coordination material; never authoritative at any tier above this one (DS-DEV-025).

**No ADR — new, superseding, or otherwise — may weaken or override `SECURITY_RULES.md`, `TRADING_RULES.md`, the Risk Engine's independent authority, deterministic financial truth, or any mandatory `TradeValidationPipeline` safeguard.** Superseding an ADR (DS-ADR-006) supersedes only that ADR's own prior decision; it never supersedes tier 1's mandatory safety governance, over which no ADR has authority in the first place. When two sources at the *same* tier conflict, or the applicable tier is itself ambiguous, work stops for Owner/governance resolution rather than the conflict being silently resolved by document number, recency, or tier alone. A more specific lower-tier requirement may refine or add detail to a higher-tier rule but never contradict it; a refinement that would contradict is a defect to correct at the lower tier, not a valid exception.

**Acceptance Criteria:**
- No Approved ADR's Decision contradicts `SECURITY_RULES.md`, `TRADING_RULES.md`, DS-RSK-001/DS-PRD-006's Risk Engine authority, DS-PRD-004/ADR-003's deterministic-financial-truth rule, or DS-EXE-001/DS-API-EXE-001's pipeline safeguards.
- No Codex-internal conflict is resolved solely by "lower document number wins" where the conflict falls outside both sources' declared scope, or by tier alone where tiers are equal or ambiguous — Owner/governance resolution is required instead.
- A conflict between two tier-1 sources (e.g., an apparent tension between `SECURITY_RULES.md` and `TRADING_RULES.md`) stops work for explicit resolution rather than being silently decided by this document.
- Every recorded Codex-internal conflict in this session's history (e.g., the DS-005-A03/A05, DS-006-H2, DS-007-H1 findings) was resolved through the audit/repair process this hierarchy describes, not by silent precedence.

**Testing:** Cross-document contradiction check between every Approved ADR and tier-1 sources, performed on every ADR revision; cross-volume contradiction check (shared with DS-ADR-001/007's own tests).

## 8. Traceability and Implementation Responsibility

### DS-ADR-011 — Traceability Expectations

**Release Classification:** Committed / MVP | **Governing Source:** DS-QA-018 (Committed); DS-002 §5.5

**Description:** Every ADR cited as a Governing Source by a DS-002 through DS-011 requirement is included in `docs/traceability/TRACEABILITY_MATRIX.csv`'s Design/ADR column, per DS-002 §5.5's five-stage traceability model. This requirement does not redefine DS-QA-018's traceability architecture; it confirms ADRs are within its scope.

**Acceptance Criteria:** Matches DS-QA-018's acceptance criteria, extended explicitly to `ADR-NNN` IDs.

**Testing:** Traceability-completeness audit (shared with DS-QA-018's own test), including ADR-ID rows.

### DS-ADR-012 — Implementation and Review Responsibilities

**Release Classification:** Committed / MVP | **Governing Source:** `AGENTS.md` "Critical Code Review"; DS-SCA-021 (Committed); DS-DEV-007 (DS-010, Committed)

**Description:** Implementing an Approved ADR's decision in code follows the same independent-review discipline DS-SCA-021/DS-DEV-007 already establish for security-critical and major changes generally — no single agent both implements an ADR-governed change and solely approves it, for decisions of ADR-001–004's scope (safety boundaries, calculation authority).

**Acceptance Criteria:** Matches DS-SCA-021/DS-DEV-007's acceptance criteria exactly, applied to ADR-implementing changes.

**Testing:** Code-review process audit (shared with DS-SCA-021/DS-DEV-007's own tests).

## 9. Index of Existing ADRs

The following table indexes the four existing, Approved ADRs. This index summarizes; the `ADR-NNN` files linked below remain the sole authoritative record of each decision. No decision content is restated or altered here.

| ID | Title | Status | Version | Owner | Summary | Related Governing Volumes |
|---|---|---|---|---|---|---|
| [ADR-001](ADR-001-Desktop-First-Application.md) | Desktop-First Application | Approved | 1.1.0 | TheSinnerMan | DarkSage is desktop-first while preserving future service/API extensibility. | DS-001 §20; DS-ARC-002/003; DS-DEV-002 |
| [ADR-002](ADR-002-Sage-Cannot-Bypass-the-Risk-Engine.md) | Sage Cannot Bypass the Risk Engine | Approved | 1.1.0 | TheSinnerMan | Sage may advise and calculate; Sage cannot bypass or silently override the Risk Engine. | DS-001 §13; DS-PRD-006; DS-RSK-001; DS-ARC-011/012; DS-SCA-012/015; DS-QA-006 |
| [ADR-003](ADR-003-Deterministic-Financial-Calculations.md) | Deterministic Financial Calculations | Approved | 1.1.0 | TheSinnerMan | Material financial calculations shall use deterministic implementations rather than generative model output. | DS-001 §9/§11; DS-PRD-004; DS-RSK-002; DS-DEV-019; DS-QA-004/005 |
| [ADR-004](ADR-004-Presentation-Independence.md) | Presentation Independence | Approved | 1.1.0 | TheSinnerMan | Workspace layout and widget visibility shall not determine enabled analytical capability or Sage evidence availability. | DS-001 §16; DS-PRD-003; DS-WKS; DS-UX-001 |

## 10. Process for Adding Future ADRs

1. Confirm the decision meets DS-ADR-008's "required" bar (not DS-ADR-009's "not required" category).
2. Draft the ADR using `docs/templates/markdown/ADR.md`, populating Document Control, Context, Decision, Consequences, Alternatives Considered, and Related Requirements.
3. If the decision changes a prior Approved ADR, name it explicitly as superseded (DS-ADR-006) rather than silently reinterpreting it.
4. Route for approval per DS-ADR-003 (Owner, or Keeper within Keeper Delegated Authority's scope).
5. On approval, set Status to Approved, record the Decision History entry, and update this document's §9 Index in the same or a following DS-012 revision.
6. Update `docs/traceability/TRACEABILITY_MATRIX.csv` per DS-ADR-011.

## 11. Non-Goals

DS-012 does not: restate, alter, or weaken any existing ADR's Decision content (§9 indexes only); decide new architecture itself (a genuinely new decision is proposed as a new `ADR-NNN` file, not written into DS-012); duplicate the ADR files as a second, competing authority (DS-ADR-001 fixes this as a permanent constraint); or itself contain the retrofitted Context/Consequences/Alternatives Considered/Related Requirements content for ADR-001 through ADR-004 — that retrofit has been completed directly in the four ADR files as part of the consolidated Codex cleanup pass (see §13); DS-012 only indexes them (§9) and does not duplicate their content.

## 12. Dependencies

- [DS-001](../Volume-01-Foundation/DS-001-Executive-Vision.md) §11, §23
- [ADR-001](ADR-001-Desktop-First-Application.md), [ADR-002](ADR-002-Sage-Cannot-Bypass-the-Risk-Engine.md), [ADR-003](ADR-003-Deterministic-Financial-Calculations.md), [ADR-004](ADR-004-Presentation-Independence.md)
- `docs/templates/markdown/ADR.md`
- `.ai-workflow/KEEPER_AUTHORITY.md`, `DECISION_LOG.md`
- `docs/traceability/TRACEABILITY_MATRIX.csv`

## 13. Risks and Constraints

- **Existing ADRs' template sections are complete:** ADR-001 through ADR-004's Context, Consequences, Alternatives Considered, and Related Requirements sections were retrofitted in the consolidated Codex cleanup pass, grounded in already-approved DS-001/002/003/004/007/009 content (each ADR bumped 1.0.0 → 1.1.0). No ADR's Decision, Status, or approval authority changed. This entry previously recorded the gap as a non-blocking editorial item deferred to that pass; it is retained here, corrected, for revision-history traceability rather than removed outright.
- **No competing authority:** every DS-ADR-NNN requirement in this document was checked to ensure it governs process (lifecycle, approval, indexing) rather than restating any ADR's substantive Decision text, per the explicit instruction that DS-012 must not create duplicate architectural authority.
- **Conflict-resolution hierarchy is new:** DS-ADR-010 is the first explicit statement of how Codex-internal (not just root-document) conflicts are resolved; it codifies practice this session has already followed (every prior repair pass resolved a conflict through audit/repair, never by silent document-number precedence) rather than introducing new behavior.

## 14. Verification Approach

Each `DS-ADR-NNN` requirement states its own Testing. Document-level verification (unique-ID check, §9 index accuracy against the four existing ADR files, no restated/altered ADR decision content, no contradiction with DS-001 through DS-011) recorded in `.ai-workflow/HANDOFF.md`.

## 15. References

- `docs/codex/Volume-12-ADRs/ADR-001-Desktop-First-Application.md` through `ADR-004-Presentation-Independence.md`
- `docs/templates/markdown/ADR.md`
- [DS-001](../Volume-01-Foundation/DS-001-Executive-Vision.md) §11, §23
- `.ai-workflow/KEEPER_AUTHORITY.md`, `DECISION_LOG.md`

## Appendix A — Open Questions

1. **RESOLVED in the consolidated Codex cleanup pass.** Context, Consequences, Alternatives Considered, and Related Requirements were retrofitted into ADR-001 through ADR-004 (each bumped to Version 1.1.0), grounded in already-approved DS-001/DS-002/DS-003/DS-004/DS-007/DS-009 content, with no change to any Decision, Status, or approval authority. Retained here for revision-history traceability, not as an open item.
2. **Future ADR candidates already implied by open questions elsewhere in this Codex** — e.g., the authentication token mechanism (DS-006 Appendix A #2) and the database-migration trigger (DS-004 Appendix A #1) are plausible future ADR topics once decided, per DS-ADR-008; not created preemptively here.
3. **Governance-confirmation carryover** — the standing `BLOCKERS.md` items (`ROADMAP.md` phase boundaries as Codex release-scope authority; phase-mapping precision) are unaffected by DS-012 and not re-litigated here.
