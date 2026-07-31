# DarkSage Feature Governance

| Field | Value |
|---|---|
| Document | Feature Governance |
| Version | 0.1.0 |
| Status | Draft (Foundation Pass) |
| Owner | TheSinnerMan |
| Owning Volume | DS-022 (`docs/codex/Volume-22-ProductExperience/`) |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

This document governs the Complete Features System (`docs/features/`): how a feature gets an ID, who owns it, how its status may change, and — critically — the **controlled-ID family registry** for the new DS-015–DS-023 expansion, including how naming collisions against existing DS-002/DS-007 families were resolved. This governance is additive to the Core Codex; it does not alter any DS-001–DS-014 requirement, ID, or classification.

## 1. Feature Identifier Scheme

`feature_id` (format `FEAT-NNNN`) is a **catalog-internal identifier, not a controlled Codex requirement ID**. It is deliberately kept out of the `DS-<DOMAIN>-NNN` / `ADR-NNN` / `DSF-NNN` namespaces so the fast-growing, exploratory feature catalog never collides with, or pollutes the counting of, the Core Codex's controlled-ID inventory (currently 459 requirement IDs / 484 broader controlled IDs, per the independently-verified Core Codex). A `FEAT-NNNN` row's `owner_volume`, `supporting_volumes`, and `dependencies` fields cross-reference real controlled IDs where they exist; the feature_id itself is never cited as a controlling requirement source.

## 2. Ownership Rule

**Every feature has exactly one primary `owner_volume`.** Supporting volumes (`supporting_volumes`) may be multiple. This is mechanically checkable (see §5) and is enforced the same way the Core Codex enforces "no controlled ID has two definitions."

## 3. Controlled-ID Family Registry (DS-015–DS-023 Expansion)

Before allocating any new family, every existing family in the Codex was enumerated (via `scripts/publication/validate_publication.py`'s `collect_controlled_definitions_with_locations()`). Four proposed families from the foundation instructions collided with existing, locked DS-002/DS-007 families and were resolved as follows — **no existing family was renamed, renumbered, or reinterpreted; only the newly-proposed name was adjusted or the existing family was reused instead of duplicated.**

**Ownership model (2026-07-26 audit repair):** for every controlled family below, `DS-022` is stewarded as the owner only where the family's content is genuinely design-system/interaction-only. Where a family encodes normative trading/data/business behavior, the primary owner is the relevant functional volume (typically `DS-002`, the Core product-requirements volume that already owns sibling families `DS-CHT`/`DS-ALT`/`DS-STR`/`DS-SCN`/`DS-MKT`), and `DS-022` is demoted to a supporting volume for UX/interaction requirements only. This is not a mechanical rebalancing of ownership counts; each reassignment below is justified on its own content.

| Proposed Family | Collision? | Resolution |
|---|---|---|
| DS-EDN (Editions) | No | New family, owned by DS-015. |
| DS-PLT (Platforms) | No | New family, owned by DS-016. |
| DS-LOC (Local-First Architecture) | No | New family, owned by DS-017. |
| DS-SYG (Sage Deployment) | No (distinct from existing DS-SGE) | New family, owned by DS-018. Deliberately distinct from DS-SGE (DS-003, Sage *behavioral* requirements), which is unchanged. |
| DS-SUB (Subscriptions) | No | New family, owned by DS-019. |
| DS-ENT (Entitlements) | No | New family, owned by DS-019. |
| DS-MUA (Multi-User/Multi-Account) | No | New family, owned by DS-020. |
| DS-EXT (Stop-Loss/Take-Profit/Exit Management) | No (distinct from existing DS-EXE) | New family, owned by DS-020. Deliberately distinct from DS-EXE (DS-002, order execution/broker integration generally), which is unchanged. |
| DS-DVT (Device Trust) | No | New family, owned by DS-021. |
| **DS-UX** (Product Experience) | **Yes** — DS-UX already exists, owned by DS-007 (25 existing requirements). | **Reused, not duplicated.** DS-007 remains sole owner of existing DS-UX-NNN requirements; DS-022 is a supporting/cross-referencing volume for new expansion-scope entries filed under the same existing family. |
| DS-DSN (Design System) | No | New family, owned by DS-022. |
| DS-FTR (Feature Governance) | No | New family, owned by DS-022. |
| **DS-OPS** (Operations) | **Yes** — DS-OPS already exists, owned by DS-002 (4 existing requirements, `DS-OPS-Operations.md`). | **Reused/extended, not duplicated.** DS-002's existing DS-OPS-001-through-NNN entries are unchanged; DS-023 is where new expansion-scope DS-OPS-NNN entries are authored going forward (additive numbering only, never a renumber). |
| DS-REC (Recovery) | No | New family, owned by DS-023. |
| DS-DPR (Data Provenance) | No | New family, owned by DS-023. |
| DS-OBS (Observability) | No | New family, owned by DS-023. |
| DS-CST (Cost Controls) | No | New family, owned by DS-023. |
| **DS-CHT** (Charting) | **Yes** — DS-CHT already exists, owned by DS-002 (5 existing requirements, `DS-CHT-Charts.md`). | **Reused, not duplicated.** New charting-expansion requirements (multi-chart layouts, synchronized crosshairs, etc.) continue the existing DS-CHT numbering; DS-022 stewards the feature-catalog entries and UX presentation. |
| DS-DRW (Drawing Tools) | No | New family. **Resolved (2026-07-26 audit repair)**: the price/level-anchored analysis drawing tools (trend lines, horizontal/vertical levels, channels, Fibonacci, support/resistance, anchored VWAP) are owned by DS-002 (they encode normative technical-analysis semantics, not just rendering). Pure annotation/UX tools with no independent analytical content (notes/callouts, drawing templates, locking/hiding) remain DS-022-owned. DS-022 is a supporting volume for all DS-DRW rendering/interaction. |
| DS-SCR (Screeners) | No | New family, owned by DS-002. **Resolved (2026-07-26 audit repair)**: DS-SCR is user-configurable, ad-hoc filtering/scanning (custom columns, saved filters, exports, user-driven scan configuration) — distinct in scope from DS-SCN (DS-002, automated/scheduled candidate generation, monitoring, system-driven ranking). Both families are owned by DS-002 (consistent with sibling reused families DS-CHT/DS-ALT/DS-STR/DS-MKT), so there is exactly one requirement authority across both, and no overlap: a given requirement is either user-driven (DS-SCR) or system-driven (DS-SCN), never both. DS-022 is a supporting volume for screener UX/interaction only. |
| DS-WCH (Watchlists) | No | New family. **Resolved (2026-07-26 audit repair)**: primary owner is DS-002 (normative watchlist behavior — membership rules, smart-watchlist criteria, sync), consistent with sibling business-capability families. DS-022 is a supporting volume for watchlist UX/interaction only, not the primary owner. |
| **DS-ALT** (Alerts) | **Yes** — DS-ALT already exists, owned by DS-002 (4 existing requirements, `DS-ALT-Alerts.md`). | **Reused, not duplicated.** New alert-expansion requirements (multi-condition builder, escalation, signed webhooks) continue the existing DS-ALT numbering. |
| **DS-MKT** (proposed for "Market Visualization") | **Yes** — DS-MKT already exists, owned by DS-002, for **Market Data** (7 existing requirements, `DS-MKT-Market-Data.md`) — a different concept. | **Renamed to avoid collision.** The market-visualization family (heatmaps, breadth, market-regime dashboard) is instead named **DS-VIZ**. DS-MKT itself is untouched and continues to mean Market Data only. **Ownership resolved (2026-07-26 audit repair)**: DS-VIZ is owned by DS-002 (it visualizes normative market-data/portfolio-risk computations, not a design-system concern); DS-022 supports the visual/interaction layer. |
| DS-CAL (Market Calendars) | No | New family. **Resolved (2026-07-26 audit repair)**: owned by DS-002 (calendar data — earnings, holidays, Fed events, expirations — is normative market data, not UX); DS-022 supports calendar UX/interaction only. |
| **DS-STR** (Strategy Customization) | **Yes** — DS-STR already exists, owned by DS-002 (4 existing requirements, `DS-STR-Strategies.md`). | **Reused, not duplicated.** Strategy-customization requirements (visual builder, restricted language, indicator builder) continue the existing DS-STR numbering; DS-022 stewards UX presentation. |
| DS-ECO (Creator/Ecosystem) | No | New family. **Resolved (2026-07-26 audit repair)**: owned by DS-002 (creator/marketplace versioning and distribution are normative product-behavior requirements); DS-022 supports the creator-facing UX only. |
| **DS-DVM** (Founder Sage Developer Mode) | No | New family, owned by **DS-018** (Sage Deployment and Intelligence Architecture) — primary owner. Supporting: DS-015 (edition/repository boundary), DS-021 (sandboxing, secrets, repository security, Founder-asset exclusion), DS-023 (logging, diagnostics, rollback, recovery, resource limits). Founder-only, private, local-workstation capability; excluded from all customer builds; not required for the customer commercial release. Added 2026-07-26 per audit repair Section 8. Represented in the feature catalog as `FEAT-0268` (catalog-internal `feature_id`, not a controlled Codex requirement ID — see §1), not as a new DS-0NN volume, so it does not change the Core Codex's 459/493 controlled-ID totals. |

## 3a. Placeholder Acceptance Summaries for Distant Backlog Features (Governance Permission)

Per the 2026-07-26 audit repair, a scoped placeholder acceptance summary (e.g. `TBD -- requirement not yet fully drafted`) **remains permitted, and is not a defect,** for a feature row when **all** of the following hold:

- `implementation_status` is `Idea` or `Future` (not Planned, Blocked, or further along -- a committed status requires a real acceptance summary regardless of stage);
- `initial_release_required = No`;
- `safety_classification` is `N/A`, `Informational`, or `Advisory (Sage, non-authoritative)` -- never `Deterministic-Authoritative` (the feature is not safety-critical, not an exit-management, order-execution, automation, security, Founder/customer-separation, or recovery/reconciliation feature).

Any feature failing one of these conditions must carry a real, testable acceptance summary; `validate_feature_registry.py` enforces this distinction mechanically (see §5).

## 4. Status Transition and Evidence Rules

See `FEATURE_STATUS_DEFINITIONS.md` for the full status vocabulary and its evidence requirements. Summary of the rules a validator enforces:

- A feature cannot move to **Released** without non-empty `implementation_evidence`, `test_evidence`, and `release_evidence`.
- A feature cannot be **Tested** without non-empty `implementation_evidence` and `test_evidence`.
- A feature cannot be **Implemented** without non-empty `implementation_evidence`.
- A feature marked **Blocked** must have a non-empty, non-generic `blocker`.
- A feature marked **Deprecated** or **Removed** must have non-empty `deprecation_notes`, and either a `replacement_feature` or an explicit "no replacement" statement within `deprecation_notes`.
- A feature marked `initial_release_required = Yes` cannot have `implementation_status = Future` without an explanation recorded in `deprecation_notes` or `blocker` (a Future item cannot silently also be a release requirement).
- No feature whose `edition_availability` includes only `Founder` may appear with `Customer` in its `platform_availability`/edition matrix row — i.e. no Founder-only capability may be marked available in the Customer Edition.
- No feature whose `groundwork_required_now = Explicitly Rejected` may simultaneously carry `implementation_status = Planned` (an explicitly-rejected capability is never "Planned").
- A feature marked **Designed** must carry real `design_evidence` — a citation to an actual document/section, ADR, or controlled requirement. Empty, `None`, `N/A`, `Not Yet Designed`, `This registry entry`, or any other recognized placeholder is **not** acceptable evidence for Designed status (2026-07-26 second audit repair). `Not Yet Designed` remains an acceptable *evidence value* for a non-Designed status (Idea/Planned/etc.) — it only becomes a defect when the status claimed is Designed.
- A feature marked **Removed** must carry both removal evidence and migration/cleanup/disposition evidence where user data or a dependent feature could be affected; a generic `deprecation_notes` entry alone is not sufficient (2026-07-26 second audit repair).

## 4a. Dependency Graph Authority (Canonical Statement)

**`FEATURE_DEPENDENCIES.csv` is the single canonical source of truth for the feature dependency graph.** The `dependencies` column in `FEATURE_REGISTRY.csv` is a **derived, generated summary** of that canonical file — it is never hand-edited independently, and `validate_feature_registry.py` mechanically enforces that the two remain exactly equal for every feature. This is normative governance, not merely a changelog note; it applies to every present and future edit to either file.

**Dependency cycles are prohibited.** The canonical graph in `FEATURE_DEPENDENCIES.csv` must be acyclic — no feature may depend, directly or transitively, on itself. `validate_feature_registry.py` detects and fails on any cycle (self-dependency, two-node cycle, or longer cycle), reporting the exact cycle path. A cycle may be permitted only if a future, explicit, controlled exception mechanism is introduced into this governance document and the validator together; no such mechanism exists today, and none may be assumed.

## 5. Validation

Enforced by `scripts/publication/validate_feature_registry.py`: unique `feature_id`s, allowed `implementation_status`/`release_stage`/`groundwork_required_now`/`safety_classification` values, every `owner_volume` resolves to a real DS-NNN volume (DS-001–DS-023), every feature has a non-empty `release_stage`, the specific cross-field rules in §4, the dependency-graph canonical-authority and acyclicity rules in §4a, and the Designed/Removed evidence rules above. See that script's own docstring for the authoritative, current check list.

## 6. Amendment Process

Any change to this document, to a controlled-ID family assignment, or to the status/stage vocabularies is itself a feature-governance change and should be recorded in `FEATURE_CHANGELOG.md`.

## Revision History

| Version | Date | Summary |
|---|---|---|
| 0.1.0 | 2026-07-25 | Initial foundation-pass governance, including the controlled-ID family collision analysis for DS-015–DS-023. |
