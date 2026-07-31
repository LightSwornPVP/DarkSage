# DS-011 — Development Roadmap

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-011 |
| Title | Development Roadmap |
| Version | 0.5.0 |
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
| 0.5.0 | 2026-07-25 | TheSinnerMan / Keeper | Independent-audit blocker-repair (Blocker 4): corrected §6a's DS-JRN row, which had incorrectly represented DS-JRN-006 (Safe Progression, governing-classified Future/Exploratory in DS-002) as Planned and Sage/Phase-6-gated grouped together with DS-JRN-005. DS-JRN-006 is not Sage-dependent (its mechanic is education/discipline/process-consistency reward, unrelated to Sage coaching) and now carries no phase placement and no Planned classification anywhere in this document, consistent with DS-002's own governing classification. DS-JRN-005 (genuinely Sage-dependent, Planned) is unaffected. |
| 0.4.0 | 2026-07-25 | TheSinnerMan / Keeper | Independent-audit repair (H1, H3): added Phase Reference Table rows/mappings for DS-RSH (Research Intelligence), DS-JRN (Journal & Review Intelligence), and DS-ALT/Discord (Alerts & Monitoring), closing the H1 roadmap-placement gap — none previously appeared in §6's table. Renumbered the Founder Vision Completion section from the misnumbered "## 20." (skipping §§15–19) to the correct next-available "## 15." No existing phase's Purpose, Key Dependency, or Classification Note changed. |
| 0.3.0 | 2026-07-25 | TheSinnerMan / Keeper | Founder Vision Completion amendment and cross-volume traceability, including Discord notification boundaries where applicable. |
| 0.1.0 | 2026-07-24 | TheSinnerMan | First controlled draft, authored as part of the Batch 2 grouped pass (DS-010/DS-011/DS-012). Adds a Codex governance layer over the existing `ROADMAP.md` (Phase 0 through Phase 14): phase-to-Release-Classification mapping rules, entry/exit criteria discipline, the paper-first/live-later gate, and a phase reference table — without restating `ROADMAP.md`'s full deliverable lists, which remain its own authoritative content. |
| 0.2.0 | 2026-07-24 | TheSinnerMan | Targeted repair for independent-audit finding DS-011-H1 (phase dependencies and sequencing). Added `DS-RM-015` (Sequencing Categories and Exception Rule: Strict/Parallel/Optional-Deferred/Gate-chain) and a Sequencing Category column to §6's Phase Reference Table, so entry is determined by each phase's declared Key Dependency rather than assumed immediate-predecessor order. Corrected `DS-RM-004`'s mis-citation of `DS-RM-005` as a sequencing-exception mechanism (DS-RM-005 governs only Committed-depends-on-Planned defects). Corrected Phase 4's row, which falsely implied Transaction/Position (Planned, delivered within Phase 4's own scope) were pre-existing Phase-1 dependencies. `DS-RM-006` now explicitly places Phases 9–11 as Parallel/Optional tracks outside the Gate-chain rather than silently omitting them from the stated live-trading sequence. The open owner-governance question about `ROADMAP.md` classification authority (DS-RM-002) is unchanged. |
| 0.2.1 | 2026-07-24 | TheSinnerMan | Consolidated cleanup pass: replaced the blended "Planned/Future" Classification Note label on Phase 5 and Phase 8 of §6's Phase Reference Table with DS-002 §5.3's exact three-value Release Classification vocabulary (Committed/MVP, Planned, Future/Exploratory), stated per item rather than as an ambiguous hybrid. Phase 5 now lists DS-EDU-001/DS-ARC-025 as Planned and DS-EDU-002 as Future/Exploratory separately; Phase 8 now reads Future/Exploratory only, matching DS-RM-015's own definition of Optional/Deferred content. No new release-classification authority was introduced; ROADMAP.md's phase-boundary authority and DS-RM-002's still-open governance-confirmation question are unchanged. |

## 1. Purpose

DS-011 is the authoritative Codex-level statement of how DarkSage's roadmap governs Release Classification, sequencing, and gating for every other Codex volume. `ROADMAP.md` (repository root) remains the authoritative source for phase *content* — goals, deliverables, and exit criteria in full detail. DS-011 does not restate that content; it adds the governance layer every DS-002 through DS-010 requirement already relies on: the rule by which a requirement's phase maps to Committed/MVP, Planned, or Future/Exploratory, and the gates that must pass before a phase is considered complete.

## 2. Scope

This document governs: the phase-to-Release-Classification mapping rule; entry/exit criteria discipline; the no-reverse-dependency rule; the paper-first/live-later progression gate; security and risk gates; data/broker integration gates; Sage/model evolution gating (including the boundary around specialized financial-model research); mobile/iPhone progression gating; testing/QA and documentation/Codex gates; migration and compatibility considerations; post-release hardening; and the boundary around deferred research/optional modules. It includes a Phase Reference Table summarizing each `ROADMAP.md` phase's purpose, key dependency, exit-criteria source, and classification note.

DS-011 does not govern: the detailed deliverable list within any phase (`ROADMAP.md` remains authoritative); product-level requirement content (DS-002 through DS-009); development process (DS-010); or the ADR governance system (DS-012). DS-011 does not invent calendar dates or delivery promises — none are approved, and none are introduced here.

## 3. Audience

Product owners, engineering contributors, independent auditors, and future Codex authors who need to determine a feature's phase-appropriate Release Classification or a phase's readiness gate.

## 4. Definitions

See DS-001 §24 and DS-002 §4. Additional terms:

| Term | Meaning |
|---|---|
| Phase | A `ROADMAP.md`-defined stage of development (Phase 0 through Phase 14) with its own goal, deliverables, and exit criteria |
| Foundation-now / hardening-later | The pattern by which a Committed/MVP obligation's basic form is required from an early phase while its full production-grade hardening is a named later-phase deliverable — see DS-RM-003 |
| Release gate | The set of exit criteria and DS-009 test categories that must pass before a phase is recorded complete (DS-QA-017) |
| Reverse dependency | A defect in which an earlier Committed/MVP baseline requires a later phase's capability to be considered complete — prohibited by DS-RM-005 |

## 5. Roadmap Authority and Classification Rules

### DS-RM-001 — Roadmap Authority and Source of Truth

**Release Classification:** Committed / MVP | **Governing Source:** `ROADMAP.md` (repository root, authoritative); `AGENTS.md` Source-of-Truth priority order

**Description:** `ROADMAP.md` is authoritative for phase content: goals, deliverables, and exit criteria. DS-011 governs how Codex documents interpret and cite `ROADMAP.md`; it does not restate or duplicate phase deliverable lists. Where DS-011 and `ROADMAP.md` appear to differ, `ROADMAP.md`'s phase content controls per `AGENTS.md`'s document-priority order (`SECURITY_RULES.md` > `TRADING_RULES.md` > `ARCHITECTURE.md` > `PROJECT_SPEC.md` > `ROADMAP.md` > `AGENTS.md`), and the difference is recorded as a DS-011 defect to reconcile, not silently resolved in DS-011's favor.

**Acceptance Criteria:**
- No DS-011 content contradicts `ROADMAP.md`'s stated phase goals, deliverables, or exit criteria.
- A future `ROADMAP.md` change that affects DS-011's Phase Reference Table (§6) is reflected in DS-011's next revision.

**Testing:** Cross-document consistency check between DS-011 §6 and `ROADMAP.md` on every DS-011 revision.

### DS-RM-002 — Phase-to-Release-Classification Mapping Rule

**Release Classification:** Committed / MVP | **Governing Source:** DS-002 §5.3's Committed/MVP eligibility test (Committed); `ROADMAP.md`

**Description:** This requirement formalizes the interpretive convention this Codex has applied consistently since DS-002's v0.4.0 reconciliation: a requirement's Release Classification is Committed/MVP only if it is traceable to (a) a DS-001 FOUNDATIONAL PRINCIPLE, (b) an approved ADR, (c) bare technical/safety necessity for an already-Committed item, or (d) explicit `ROADMAP.md` Phase 1 scope. A requirement scoped to Phase 2 or later defaults to Planned; a requirement with no phase placement and no DS-001/ADR traceability defaults to Future/Exploratory pending an explicit owner decision. **This mapping remains the Codex's working convention, not yet a formally owner-confirmed policy** — see DS-002 Appendix A Open Question #1 and DS-004 Appendix A Open Question #4, both still open per `.ai-workflow/BLOCKERS.md`'s Owner Decision Required section; DS-011 restates the convention for consistency but does not itself close that open question.

**Acceptance Criteria:**
- Every Committed/MVP requirement across DS-002 through DS-010 traces to one of the four bases listed above (spot-checked, not re-derived, since each volume already states its own Governing Source).
- No requirement is classified Committed/MVP solely because a phase number is low, without an explicit Governing Source citation.

**Testing:** Classification-traceability spot-check across a sample of Committed/MVP requirements per volume, performed as part of DS-011's own self-verification and future cross-volume audits.

### DS-RM-003 — Foundation-Now / Hardening-Later Pattern

**Release Classification:** Committed / MVP | **Governing Source:** `ROADMAP.md` Phase 1 and Phase 12; DS-SCA-004/005/011/025/027 (all Committed); DS-ARC-018 (Committed)

**Description:** Several `ROADMAP.md` phase-12 deliverables (e.g., "Tamper-evident audit logs," "Session management," "Authentication hardening," "HTTPS/TLS," "Rate limiting") name capabilities whose *basic obligation* is already Committed/MVP from an earlier phase (audit-log integrity: DS-SCA-025/027; session lifecycle: DS-SCA-004; authentication: DS-SCA-005; secure communication: DS-SCA-011, per DS-ARC-018's staged model). This is not a contradiction: the Committed obligation is the floor that applies from the phase in which the underlying capability first exists (e.g., DS-OPS-001/002's audit-logging obligation applies from Phase 1, since the Phase-1 Risk Engine foundation already produces auditable determinations), while the phase-12-listed deliverable is the *production-grade hardening* of that same floor for always-on deployment. A downstream volume citing a Phase-12 deliverable name as if it were the entire obligation, or citing an early-phase Committed obligation as if it already included Phase-12 hardening, is misreading this pattern.

**Acceptance Criteria:**
- No Codex volume treats a Phase-12-named hardening deliverable as evidence that the underlying Committed/MVP obligation does not yet apply.
- No Codex volume treats an early-phase Committed/MVP obligation as already satisfying its Phase-12 hardening deliverable without that hardening actually being implemented.
- Every instance of this pattern (session, authentication, secure communication, audit-log integrity — the four identified in this repair) is cited explicitly wherever it recurs, rather than silently assumed.

**Testing:** Cross-volume consistency review confirming every Phase-12-named-deliverable-with-an-earlier-Committed-floor case is documented per this pattern, not treated as a defect.

## 6. Phase Reference Table

`ROADMAP.md` remains authoritative for full deliverable lists; this table summarizes purpose, key dependency, sequencing category (DS-RM-015), exit-criteria source, and DS-011's classification note per phase. Sequencing category values: **Strict** (cannot begin meaningful implementation until its Key Dependency phase(s) exit), **Parallel** (may proceed concurrently with intervening phase numbers once its own Key Dependency is met), **Optional/Deferred** (Future/Exploratory content per DS-RM-012; timing not fixed relative to other phases beyond its Key Dependency), **Gate-chain** (part of the strict paper-first/live-later sequence, DS-RM-006).

| Phase | Purpose | Key Dependency | Sequencing Category | Exit Criteria Source | Classification Note |
|---|---|---|---|---|---|
| 0 — Foundation | Establish a safe, consistent development environment | None (first phase) | Strict | `ROADMAP.md` Phase 0 | Governance/process only; no product requirements originate here |
| 1 — Core Market Intelligence | First working desktop research application | Phase 0 exits | Strict | `ROADMAP.md` Phase 1 | Committed/MVP baseline for most of DS-002/DS-004/DS-005/DS-006/DS-007's Committed requirements |
| 2 — Backtesting and Strategy Lab | Prove strategy logic historically before paper automation | Phase 1 exits (Signal, StrategyProfile models) | Strict | `ROADMAP.md` Phase 2 | Planned — DS-STR, DS-BKT families |
| 3 — Strategy Intelligence | Learn which strategies work under which conditions | Phase 2 exits (backtest infrastructure) | Strict | `ROADMAP.md` Phase 3 | Planned — DS-PERF family, DS-ARC-020 |
| 4 — Portfolio Builder | Long-term investing and portfolio intelligence | Phase 1 exits (backend/API/data foundation only) | Parallel (may proceed alongside Phases 2/3; does not require backtesting or strategy-intelligence infrastructure) | `ROADMAP.md` Phase 4 | Planned — DS-PRT family, DS-ARC-023. **Correction:** Transaction (DS-DB-025) and Position (DS-DB-009) are themselves Planned portfolio-scope data models delivered as part of this phase's own scope — they are not pre-existing Phase-1 Committed dependencies, and this phase does not depend on them already existing. |
| 5 — Pattern Recognition, Advanced Charts, Trading Knowledge Engine | Visual technical intelligence; structured trading-knowledge ingestion | Phase 1 exits (charts, indicators) | Parallel (independent of Phases 2/3/4) | `ROADMAP.md` Phase 5 | Mixed, stated per-item rather than as a single blended label: **Planned** — DS-EDU-001 (Contextual Terminology Reference), DS-ARC-025 (Trading Knowledge Engine Architecture); **Future/Exploratory** — DS-EDU-002 (Trading Knowledge Engine full capability) |
| 6 — Local AI, Cloud Providers, and Sage | Add AI assistance without making it authoritative | Phase 1 exits (deterministic core exists first) | Parallel (independent of Phases 2–5) | `ROADMAP.md` Phase 6 | Planned — DS-AI, DS-SGE families; safety boundaries (DS-PRD-001/005/006/007/011) are Committed regardless of phase, per DS-RM-002's basis (c) |
| 7 — Paper Auto-Trader | Automatically execute approved strategies in paper mode | Phase 2 exits (Strategy models); Phase 1 foundation Risk Engine; `ROADMAP.md` Phase 6's own exit criteria narratively sequence executable-trade-proposal capability after Phase 6 | Strict; also the first Gate-chain phase (DS-RM-006) | `ROADMAP.md` Phase 7 | Planned implementation; the pipeline's governance boundary (DS-EXE-001, DS-API-EXE-001, DS-SCA-012) is Committed now regardless of phase |
| 8 — Shadow Trading and Strategy Tournament | Improve strategies without risking capital | Phase 7 exits (paper execution exists) | Gate-chain (contingent — proceeds only if/when pursued, per its own Optional/Deferred content classification below) | `ROADMAP.md` Phase 8 | Future/Exploratory direction only, per DS-RM-015's definition of Optional/Deferred content — not committed by roadmap inclusion (DS-RM-012) |
| 9 — Mobile App | Make DarkSage controllable from iPhone | Phase 1 exits (backend API stable) | Parallel (independent of Phases 2–8, 10–12; does not gate or get gated by the live-trading gate chain) | `ROADMAP.md` Phase 9 | Planned — DS-MOB family, DS-ARC-003/024, DS-UX-020; mobile API-contract-readiness is a Phase-1 backend design constraint (DS-006 §7), not deferred to Phase 9 |
| 10 — Advanced Research | Deeper market and portfolio intelligence | Phase 3 and Phase 5 exit (strategy/pattern infrastructure) | Optional/Deferred, Parallel once its dependency is met (independent of Phases 6–9, 11–12) | `ROADMAP.md` Phase 10 | Future/Exploratory — no DS-002 family yet exists for most Phase 10 items |
| 11 — Options Research | Add options as a separate instrument system | Phase 2 exits (backtesting) | Optional/Deferred, Parallel once its dependency is met (independent of Phases 3–10, 12) | `ROADMAP.md` Phase 11 | Future/Exploratory — explicitly "no live options trading in this phase" |
| 12 — Production Hardening | Prepare backend for always-on deployment | Phase 7 exits (paper trading proven) | Gate-chain | `ROADMAP.md` Phase 12 | Planned; hosts the "hardening" half of the DS-RM-003 pattern |
| 13 — Limited Live Trading | Transition proven strategies to small real-money allocations | Phase 12 exits (production hardening complete) | Gate-chain | `ROADMAP.md` Phase 13 prerequisite list | Planned; gated by DS-EXE-007/DS-SCA-022 — Committed governance boundary, Planned implementation |
| 14 — Full Live Platform | Mature production trading platform | Phase 13 exits (limited live trading proven) | Gate-chain | `ROADMAP.md` Phase 14 | Future/Exploratory for full-auto mode; remains subject to deterministic risk/permissions systems at all times per `ROADMAP.md`'s own closing statement |

Phases 9, 10, and 11 are Parallel/Optional tracks: they may proceed concurrently with Phase 8 and Phase 12 once their own Key Dependency is met, and their progress or timing has no bearing on entry into the Gate-chain sequence (DS-RM-006). They are not omitted from this Codex's sequencing logic — they simply do not belong to the Gate-chain category.

## 6a. Cross-Cutting Family Phase Mapping (added in the independent-audit H1 repair)

`ROADMAP.md` predates the DS-RSH (Research Intelligence), DS-JRN (Journal & Review Intelligence), and DS-ALT (Alerts & Monitoring, including Discord) requirement families and does not name a dedicated phase for any of the three, which is the gap independent audit finding H1 identified — none of the three previously appeared anywhere in §6's table. This section maps each to its Key Dependency and Sequencing Category using the same DS-RM-002/DS-RM-015 rules §6 applies to every `ROADMAP.md`-named phase, without inventing a new numbered phase or an unsupported MVP commitment.

| Family | Purpose | Key Dependency | Sequencing Category | Classification Note |
|---|---|---|---|---|
| DS-ALT (Alerts & Monitoring, incl. Discord) | Notify users of market/watchlist/risk conditions without requiring continuous screen attention | Phase 1 exits (market data, scanner, risk foundation) | Parallel (independent of Phases 2–14; may enter once Phase 1's data/risk foundation exists) | Planned — DS-ALT-001/002/003 family; DS-ALT-004 (Discord) and DS-INT-006 additionally benefit from, but do not require, Phase 6's Sage summarization capability for richer daily/weekly report content |
| DS-RSH (Research Intelligence) | Evidence-governed news/filings/earnings/macro/insider/political research and thesis monitoring | Phase 1 exits (market data foundation) for evidence ingestion/storage; Phase 6 exits (Sage) for the bounded Sage research workflow (DS-RSH-006) specifically | Parallel (independent of Phases 2–5, 7–14; evidence ingestion/storage per DS-ARC-026 does not require Sage to exist, only DS-RSH-006's Sage-orchestrated workflow does) | Planned — DS-RSH family; DS-RSH-006 is additionally gated by Phase 6 per DS-RM-009's Sage-gating rule |
| DS-JRN (Journal & Review Intelligence) | Structured trade journal, daily/weekly review, and Sage coaching | Phase 4 exits (Portfolio/Transaction data, DS-PRT) for deterministic performance figures; Phase 6 exits (Sage) for Sage-drafted review commentary (DS-JRN-005) specifically | Parallel (independent of Phases 2–3, 5, 7–14; journal capture per DS-ARC-027 does not require Sage to exist, only DS-JRN-005's Sage coaching does) | Planned — DS-JRN-001 through DS-JRN-005 and DS-JRN-007; DS-JRN-005 is additionally gated by Phase 6 per DS-RM-009's Sage-gating rule. **DS-JRN-006 (Safe Progression) is Future/Exploratory, not Planned, and is not Sage-dependent** — its education/discipline/process-consistency reward mechanic has no Sage-coaching relationship and is corrected here (independent-audit repair) to no longer be grouped with DS-JRN-005's Phase-6 gate; it carries no phase placement at all pending a future owner decision to promote it out of Future/Exploratory (DS-RM-012 applies: roadmap non-mention is not itself a commitment). |

**Acceptance Criteria:**
- DS-RSH, DS-JRN, and DS-ALT each appear with an explicit Key Dependency and Sequencing Category, closing the independent-audit H1 gap.
- No mapping in this table commits a delivery date or promotes any DS-RSH/DS-JRN/DS-ALT requirement beyond its own DS-002-stated Release Classification (all Planned) — this table fixes sequencing, not classification, per DS-RM-002.
- The Sage-dependent sub-requirements within each family (DS-RSH-006; DS-JRN-005 only) are called out individually rather than implying the entire family waits on Phase 6.
- DS-JRN-006 is never represented as Planned or as Sage-gated anywhere in this table — it retains DS-002's own Future/Exploratory classification and carries no phase dependency, consistent with DS-RM-002 (this table fixes sequencing for committed/planned direction; it does not promote a Future/Exploratory item).

**Testing:** Sequencing-category completeness audit, extended to this table (shared with DS-RM-015's own test).

## 7. Sequencing and Gating

### DS-RM-004 — Entry and Exit Criteria Discipline

**Release Classification:** Committed / MVP | **Governing Source:** `ROADMAP.md` (per-phase exit criteria); DS-QA-016/017 (both Committed)

**Description:** A phase's `ROADMAP.md` exit criteria are the authoritative gate for that phase, tested per DS-QA-016 (End-to-End Workflow Testing) and recorded per DS-QA-017 (Release Gates). A phase's entry criteria are its explicitly declared Key Dependency, per §6's table — **not automatically its immediate numeric predecessor** — categorized per DS-RM-015's sequencing-category vocabulary (Strict, Parallel, Optional/Deferred, Gate-chain). DS-RM-005 (No-Reverse-Dependency Rule) is a distinct requirement governing Committed-baseline-depends-on-Planned-capability defects within a single requirement's own acceptance criteria; it does not govern phase-entry sequencing and is never cited as a sequencing-exception mechanism (corrected in the DS-011-H1 repair, which previously conflated the two).

**Acceptance Criteria:** Matches DS-QA-016/017's acceptance criteria exactly, applied per phase using §6's Key Dependency mapping.

**Testing:** Phase-exit-criterion E2E test suite (shared with DS-QA-016's own test); release-gate checklist execution (shared with DS-QA-017's own test).

### DS-RM-005 — No-Reverse-Dependency Rule

**Release Classification:** Committed / MVP | **Governing Source:** This Codex's established field-splitting pattern (DS-005-A03/A05, DS-006 H2, DS-007 DS-UX-016/022 repairs)

**Description:** An earlier Committed/MVP baseline shall never require a later phase's capability to be considered complete or correctly implemented. Where a Committed/MVP requirement's natural topic spans phases (e.g., a Phase-1 API endpoint whose full feature set is a Phase-2+ capability), the Committed/MVP core is split from the Planned extension using the field-splitting pattern already established throughout this Codex (DS-DB-005/007, DS-API-WKS-001/002, DS-UX-016/022) — never by silently promoting the later-phase capability to Committed, and never by leaving the earlier baseline's completeness implicitly dependent on work that has not happened yet.

**Acceptance Criteria:**
- No audit of this Codex has found (or, once found, left unresolved) a Committed/MVP requirement whose acceptance criteria cannot be satisfied without a Planned-only capability existing first — every instance found to date (DS-005-A03/A05, DS-006-H2, DS-007-H1) was repaired using this exact pattern.
- A future instance of this defect is repaired the same way: split, not promote.

**Testing:** Committed-depends-on-Planned regression check, performed as part of every volume's self-verification and cross-volume consistency pass (established practice throughout this Codex).

### DS-RM-006 — Paper-First / Live-Later Progression Gate

**Release Classification:** Committed / MVP | **Governing Source:** `ROADMAP.md` Phase 7/8/12/13/14; DS-EXE-007, DS-SCA-022 (both Committed); `AGENTS.md` "Paper Trading Only During Development"

**Description:** DarkSage progresses through the **Gate-chain** (DS-RM-015): Phase 7 (Paper Auto-Trader) → Phase 8 (Shadow Trading and Strategy Tournament) → Phase 12 (Production Hardening) → Phase 13 (Limited Live Trading) → Phase 14 (Full Live Platform). No development agent may enable real-money trading; execution work targets simulation, shadow trading, or paper trading until the explicitly approved live phase. Progression to Phase 13 requires every prerequisite `ROADMAP.md` Phase 13 lists (independent security review, independent trading-safety review, acceptable paper results, reviewed live broker adapter, verified reconciliation/kill switch/duplicate-order prevention/data health, explicit user unlock) — restated at the governance level by DS-EXE-007 and, for its security-specific content, by DS-SCA-022. DS-011 does not redefine either gate's prerequisite list; it fixes the phase sequence they sit within. **Phases 9 (Mobile), 10 (Advanced Research), and 11 (Options Research) are Parallel/Optional tracks (§6, DS-RM-015), not part of the Gate-chain** — they are not omitted from this progression; they simply do not gate it and are not gated by it. They may proceed concurrently with Phase 8 and Phase 12 once their own Key Dependency is met, and their status has no bearing on Gate-chain entry at Phase 13.

**Acceptance Criteria:** Matches DS-EXE-007/DS-SCA-022's acceptance criteria exactly; no Gate-chain phase after 7 is reachable out of the stated order; Phase 9/10/11 progress or non-progress never blocks or accelerates Gate-chain entry.

**Testing:** Live-trading gate checklist execution (shared with DS-EXE-007/DS-SCA-022's own tests).

## 8. Domain-Specific Gates

### DS-RM-007 — Security and Risk Gate Mapping

**Release Classification:** Committed / MVP | **Governing Source:** DS-SCA-007, DS-SCA-022 (both Committed); DS-EXE-007 (Committed)

**Description:** High-risk actions (enabling live trading, changing live broker credentials, increasing major risk limits, Emergency Flatten, re-enabling trading after a security event) require strong authentication (DS-SCA-007) regardless of phase, as a Committed governance boundary; their implementation timing follows §6/§7's phase sequence. The Phase-13 live-trading gate's security-specific content is DS-SCA-022's review checklist.

**Acceptance Criteria:** Matches DS-SCA-007/022's acceptance criteria exactly.

**Testing:** Requirements/design review for each high-risk-action implementation (shared with DS-SCA-007's own test).

### DS-RM-008 — Data and Broker Integration Gates

**Release Classification:** Committed / MVP | **Governing Source:** DS-ARC-006 (Committed); DS-EXE-006 (Planned); DS-SCA-013/014 (both Planned, Phase 7)

**Description:** Market-data provider integration is gated by the provider-adapter abstraction (DS-ARC-006, Committed from Phase 1). Broker integration is gated by the Broker Adapter abstraction (DS-EXE-006, Planned, Phase 7) and its least-privilege/reconciliation controls (DS-SCA-013/014). No feature integrates a data or broker provider by any path other than the applicable adapter, regardless of phase.

**Acceptance Criteria:** Matches DS-ARC-006/DS-EXE-006's acceptance criteria exactly.

**Testing:** Provider-substitution test (shared with DS-ARC-006's own test); broker permission-scope audit and reconciliation-mismatch test (shared with DS-SCA-013/014's own tests, Phase 7).

### DS-RM-009 — Sage and Model Evolution Gate

**Release Classification:** Planned, Phase 6 (governance boundary Committed) | **Governing Source:** `ROADMAP.md` Phase 6; DS-PRD-001/011 (both Committed); DS-SCA-008 (Committed)

**Description:** Sage's introduction (local model manager, provider abstraction, Sage chat) is Phase 6, gated by the deterministic core (Phases 1–5) already existing and by the AI-output-validation/model-independence boundaries (DS-PRD-001/011, DS-SCA-008) that apply unconditionally regardless of phase. Specialized, domain-specific financial-forecasting models (beyond the general-purpose local/cloud AI provider abstraction `ROADMAP.md` Phase 6 already scopes) are Future/Exploratory research, not committed by this roadmap; such research directions belong in the Idea Parking Lot volume (DS-014, not yet authored) rather than being introduced as a DS-011 commitment.

**Acceptance Criteria:**
- No Phase-6 Sage capability is classified Committed/MVP by virtue of this gate; the gate fixes sequencing, not classification (DS-RM-002 governs classification).
- No specialized financial-model research direction is introduced as a Planned or Committed requirement in this document.

**Testing:** Zero-cloud-provider functional test (shared with DS-ARC-014's own test, Phase 6); requirements-review check confirming no financial-model research is prematurely committed.

### DS-RM-010 — Mobile Progression Gate

**Release Classification:** Planned, Phase 9 | **Governing Source:** `ROADMAP.md` Phase 9; DS-ARC-003, DS-ARC-024 (both Planned); DS-UX-020 (Planned); DS-006 §7 (Committed, mobile-ready-by-design constraint)

**Description:** The mobile client is Phase 9, gated by the backend API already being stable (Phase 1) and mobile-ready-by-design (DS-006 §7's Committed constraint that every Committed/MVP endpoint is designed mobile-ready from the start, even though the mobile client itself is Phase 9). Mobile-specific security hardening (DS-ARC-024) and UI parity (DS-UX-020) implement in Phase 9.

**Acceptance Criteria:** Matches DS-ARC-003/024's acceptance criteria exactly; DS-006 §7's mobile-readiness constraint is verified against Committed/MVP endpoints continuously, not deferred to Phase 9.

**Testing:** Cross-client state-consistency test (shared with DS-ARC-003's own test, Phase 9).

### DS-RM-011 — Testing, Documentation, and Codex Gates

**Release Classification:** Committed / MVP | **Governing Source:** DS-QA-016/017 (both Committed); DS-001 §11 (Constitution #12, Committed)

**Description:** Every phase's exit criteria require DS-QA-016's E2E coverage before the phase is recorded complete (DS-QA-017). Per DS-001 Constitution #12 (Codex-Driven Engineering), a phase's features enter the Codex — as DS-002+ requirements or an ADR — before implementation, not after; DS-011's Phase Reference Table (§6) is updated in the same revision as any `ROADMAP.md` phase change that affects classification.

**Acceptance Criteria:** Matches DS-QA-016/017's acceptance criteria exactly, plus the Codex-entry-before-implementation rule.

**Testing:** Phase-exit-criterion E2E test suite; documentation-currency review checklist item (shared with DS-DEV-012's own test).

### DS-RM-012 — Deferred Research and Optional Modules

**Release Classification:** Committed / MVP (governance boundary) | **Governing Source:** `ROADMAP.md` Phase 8/10/11; DS-002 §5.3 (Committed)

**Description:** Phase 8 (Shadow Trading and Strategy Tournament), Phase 10 (Advanced Research), and Phase 11 (Options Research) are Planned/Future direction only, as `ROADMAP.md` itself states — their inclusion in the roadmap's phase sequence does not, by itself, commit any specific deliverable within them to Planned or Committed status. Each deliverable within these phases requires its own dedicated DS-002+ requirement, classified per DS-RM-002, before it is anything more than a directional placeholder. This mirrors the eligibility rule DS-013 (Feature Backlog) and DS-014 (Idea Parking Lot) will apply once authored: presence in a backlog or idea-parking document, or in a roadmap phase's deliverable list, never itself promotes an item to Committed or Planned.

**Acceptance Criteria:**
- No Phase 8/10/11 deliverable is cited elsewhere in this Codex as Committed or Planned without its own dedicated requirement.
- Future DS-013/DS-014 authoring does not silently promote a listed idea/backlog item by virtue of inclusion.

**Testing:** Requirements-review check confirming no roadmap-only mention is treated as a committed requirement.

## 9. Migration, Compatibility, and Post-Release Hardening

### DS-RM-013 — Migration and Compatibility Gate

**Release Classification:** Committed / MVP | **Governing Source:** `ROADMAP.md` Phase 12; DS-ARC-016 (Committed); DS-DEV-022 (DS-010, Committed)

**Description:** A future database-engine migration (SQLite → PostgreSQL, and TimescaleDB only if justified) is a Phase-12 decision, not committed to current scope, per DS-ARC-016. Any such migration, or any other Phase-12 compatibility change, follows DS-DEV-022's reviewed migration/backup path — never an in-place undocumented switch.

**Acceptance Criteria:** Matches DS-ARC-016/DS-DEV-022's acceptance criteria exactly.

**Testing:** Local functional test against the current database engine (shared with DS-ARC-016's own test); migration-review checklist item (shared with DS-DEV-022's own test).

### DS-RM-014 — Post-Release Hardening

**Release Classification:** Planned, Phase 12 | **Governing Source:** `ROADMAP.md` Phase 12; DS-RM-003 (this document)

**Description:** Phase 12's hardening deliverables (always-on deployment, secure secret management, HTTPS/TLS, authentication/session hardening, rate limiting, monitoring, backups/recovery, tamper-evident audit logs, data-health monitoring, broker-reconciliation hardening, deployment rollback, security review) are the production-grade ceiling for the Committed/MVP floors DS-RM-003 identifies. Phase 12 exit criteria (backend runs independently of desktop, mobile can control backend while desktop is off, production failure modes are tested) gate progression to Phase 13.

**Acceptance Criteria:** Matches `ROADMAP.md` Phase 12's exit criteria exactly.

**Testing:** Deferred to Phase 12's own implementation timing; the foundation-now/hardening-later relationship (DS-RM-003) is verified now.

### DS-RM-015 — Sequencing Categories and Exception Rule

**Release Classification:** Committed / MVP | **Governing Source:** `ROADMAP.md`; DS-RM-004 (this document)

**Description:** Added in the DS-011-H1 repair to make phase sequencing deterministically interpretable and to correct the prior conflation of general phase-entry sequencing with DS-RM-005's distinct no-reverse-dependency rule. Every phase in §6 is categorized as exactly one of:

- **Strict** — the phase cannot begin meaningful implementation until its declared Key Dependency phase(s) reach their exit criteria (e.g., Phase 2 requires Phase 1's Signal/StrategyProfile models).
- **Parallel** — the phase's Key Dependency is satisfied once its stated prerequisite phase(s) exit, but the phase does not itself block, or get blocked by, other non-dependency phases proceeding concurrently (e.g., Phase 9 Mobile depends only on Phase 1's stable backend API and may proceed alongside Phases 2–8 and 10–12).
- **Optional/Deferred** — a phase whose deliverables are Future/Exploratory direction only (DS-RM-012) and whose timing is not fixed relative to any phase beyond its own Key Dependency (Phase 10, Phase 11).
- **Gate-chain** — a phase belonging to the strict paper-first/live-later sequence (DS-RM-006: Phase 7 → 8 → 12 → 13 → 14), which is Strict with respect to the other Gate-chain phases specifically.

A phase may combine categories where accurate (e.g., Phase 8 is both Gate-chain, relative to Phase 7/12, and Optional/Deferred in content classification, since its deliverables remain Future/Exploratory per DS-RM-012 pending their own dedicated requirements). Sequencing exceptions — cases where a phase's actual Key Dependency differs from what phase numbering alone would suggest — are recorded explicitly in §6's Key Dependency column; they are never inferred silently, and DS-RM-005 is never used as their basis.

**Acceptance Criteria:**
- Every phase in §6 carries exactly one primary sequencing category (Strict, Parallel, Optional/Deferred, or Gate-chain), with combinations stated explicitly where applicable.
- No phase's entry is determined by "immediate predecessor phase number" alone where its declared Key Dependency names a different, earlier phase.
- DS-RM-005 is never cited as a sequencing-exception mechanism; sequencing exceptions are recorded under this requirement instead.
- Every phase (0 through 14) appears in §6 with a sequencing category — none are omitted from the sequencing logic.

**Testing:** Sequencing-category completeness audit against §6, confirming every phase is categorized and every category assignment matches its stated Key Dependency.

## 10. Non-Goals

DS-011 does not: restate `ROADMAP.md`'s full per-phase deliverable lists (§6 summarizes; `ROADMAP.md` remains the detailed source); invent calendar dates, delivery promises, or commitments beyond what `ROADMAP.md` and DS-002 through DS-010 already approve; formally resolve the open Owner Decision on whether `ROADMAP.md` phase boundaries are the confirmed authority for Release Classification (DS-RM-002 restates the working convention without closing that open question); or promote any Phase 8/10/11/Future-Exploratory item to Committed or Planned by virtue of appearing in this roadmap (DS-RM-012).

## 11. Dependencies

- [DS-001](../Volume-01-Foundation/DS-001-Executive-Vision.md), [DS-002](../Volume-02-Product/DS-002-SRS.md), [DS-004](../Volume-04-Architecture/DS-004-Technical-Architecture.md), [DS-006](../Volume-06-API/DS-006-API-Specification.md), [DS-008](../Volume-08-Security/DS-008-Security-Architecture.md), [DS-009](../Volume-09-Testing/DS-009-Testing-and-QA.md), [DS-010](../Volume-10-Standards/DS-010-Development-Standards.md)
- `ROADMAP.md`, `PROJECT_SPEC.md`, `AGENTS.md`
- `.ai-workflow/BLOCKERS.md` (Owner Decision Required section — phase-boundary-authority open question)

## 12. Risks and Constraints

- **Classification-authority open question:** DS-RM-002 formalizes this Codex's working convention for mapping phase to Release Classification, but the underlying question (whether `ROADMAP.md` phase boundaries are the owner-confirmed authority for Codex Release Classification) remains open per `.ai-workflow/BLOCKERS.md`. DS-011 does not close it — it documents the convention every other volume already relies on, pending that confirmation.
- **Foundation-now/hardening-later pattern:** DS-RM-003 is a new, explicit articulation of a pattern that was previously implicit across DS-006/DS-008; recording it here reduces the risk of a future author misreading a Phase-12 deliverable name as evidence an earlier Committed obligation does not yet apply (or vice versa).
- **No reverse dependencies found outstanding:** every known instance of DS-RM-005's prohibited pattern was already repaired in a prior batch (DS-005-A03/A05, DS-006-H2, DS-007-H1); DS-RM-005 exists to keep future authors from reintroducing it, not because an open instance remains. DS-RM-005 governs only that specific defect (a Committed baseline depending on Planned-only capability) — it is not a general sequencing-exception mechanism; DS-RM-015 now owns that role.
- **Sequencing correction (DS-011-H1):** DS-RM-004 previously implied phase entry follows the immediate numeric predecessor by default; §6's Key Dependency column always named the actual prerequisite (which for Phases 4–6, 9–11 is not the immediate predecessor), so the two were inconsistent. DS-RM-015 now makes the Strict/Parallel/Optional-Deferred/Gate-chain categorization explicit for every phase, and Phase 4's row no longer misstates Transaction/Position (Planned, delivered within Phase 4's own scope) as pre-existing Phase-1 dependencies. Phases 9–11 are now explicitly placed as Parallel/Optional tracks outside the Gate-chain (DS-RM-006), rather than being silently absent from the stated live-trading sequence.

## 13. Verification Approach

Each `DS-RM-NNN` requirement states its own Testing. Document-level verification (unique-ID check, §6 Phase Reference Table consistency against `ROADMAP.md`, no Committed requirement depending on a Planned-only capability, no roadmap-only item silently promoted) recorded in `.ai-workflow/HANDOFF.md`.

## 14. References

- `ROADMAP.md`, `PROJECT_SPEC.md`, `AGENTS.md`
- `docs/codex/Volume-02-Product/DS-002-SRS.md`
- `docs/codex/Volume-04-Architecture/DS-004-Technical-Architecture.md`
- `docs/codex/Volume-06-API/DS-006-API-Specification.md`
- `docs/codex/Volume-08-Security/DS-008-Security-Architecture.md`
- `docs/codex/Volume-09-Testing/DS-009-Testing-and-QA.md`
- `docs/codex/Volume-10-Standards/DS-010-Development-Standards.md`

## Appendix A — Open Questions

1. **`ROADMAP.md` phase boundaries as Codex release-scope authority** — unchanged from DS-002 Appendix A #1 / DS-004 Appendix A #4; DS-RM-002 restates the working convention without closing it.
2. **Specialized financial-model research scope** — DS-RM-009 defers this to a future DS-014 (Idea Parking Lot) entry rather than committing any direction here.
3. **Multi-monitor, live brokerage timing, PostgreSQL migration trigger, live-trading hosting provider** — unchanged from DS-002/DS-004 Appendix A; cross-referenced, not re-litigated here.

## 15. Founder Vision Completion Sequencing

The roadmap shall deliver an early recognizable DarkSage experience rather than postponing intelligence until late phases. Early desktop slices should include live/current charts, basic scanner/signal context, deterministic explanations, and a constrained Sage explanation layer. Deeper multi-step Sage research, persistent monitoring, advanced journal coaching, and specialized models may follow after their dependencies mature.

Discord notification support should enter with the general alerts/monitoring milestone: first webhook delivery, then an approved bot only if it provides material value. Full-Auto Paper remains paper-first. Restricted Full-Auto Live remains gated by security, reconciliation, operations, broker permissions, and independent approval.
