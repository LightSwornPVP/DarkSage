# DarkSage Core Codex — Foundation Completion Release

**Release date:** 2026-07-25

**Scope:** DS-001 through DS-014 and Volume-02 requirement families

**Purpose:** Repair the existing fourteen-volume foundation before authoring DS-015 and later specialized volumes.

## Added or strengthened

- Sage identity as strategist, research partner, analyst, mentor, and second set of eyes.
- Bounded multi-step Sage agency with registered tools, visible plans, auditability, and no execution bypass.
- Canonical Trade Intelligence Package across signals, charts, journal, validation, execution, alerts, and audit.
- Research Intelligence requirement family.
- Journal & Review Intelligence requirement family.
- Live streaming chart/workstation experience.
- Contextual education and mastery direction.
- Advanced portfolio intelligence and integrated strategy lifecycle.
- Five automation modes with policy-based user authority.
- Discord webhook/bot alerts and reports, disabled by default and notification-only.
- ADR-005, ADR-006, and ADR-007.

## Corrected

- Removed the contradiction that required per-order confirmation even under approved unattended paper automation.
- Clarified that Sage may prepare and hand off proposals but never approve or execute them.
- Elevated central Founder ideas from vague backlog/parking status into approved Planned direction without falsely committing them to MVP.
- Added cross-volume architecture, data, API, UX, security, testing, roadmap, backlog, and idea-disposition coverage.

## Explicitly deferred

- Creation of DS-015 and later specialized volumes.
- Any Discord-based remote trading control.
- Restricted Full-Auto Live release approval.
- Specialized/fine-tuned market models and broader experimental domains.

## Independent-Audit Repair Pass (same-day addendum, 2026-07-25)

An independent audit of this release found four High findings, all now repaired. This addendum documents exactly what changed; it does not restate the additions/corrections above, which remain as originally recorded except where H1 below corrects an overstated claim.

- **H1 — Cross-volume traceability completed for Research Intelligence, Journal & Review Intelligence, and the canonical Trade Intelligence Package.** The original "Added cross-cutting architecture, data, API, UX, security, testing, roadmap, backlog, and idea-disposition coverage" bullet above overstated what existed for these three domains at initial release — they had only unnumbered prose mentions in each downstream volume's Founder Vision Completion section, no individually identified requirements. This repair adds 23 new downstream requirement IDs: `DS-ARC-026/027/028` (DS-004); `DS-DB-028` through `DS-DB-033` (DS-005); `DS-API-RSH-001..003`, `DS-API-JRN-001..003`, `DS-API-TIP-001` (DS-006); `DS-UX-023/024/025` (DS-007); `DS-SCA-028` (DS-008); `DS-QA-024/025/026` (DS-009); and a new DS-011 §6a Cross-Cutting Family Phase Mapping table placing DS-RSH, DS-JRN, and DS-ALT/Discord against explicit Key Dependencies and Sequencing Categories. `docs/traceability/TRACEABILITY_MATRIX.csv` gained 36 new rows relative to the pre-repair baseline (23 new downstream IDs plus 13 pre-existing DS-002 product-level IDs — `DS-SIG-005`, `DS-RSH-001..006`, `DS-JRN-001..006` — that had never been traced).
- **H2 — DS-012 ADR index repaired.** §9's Index of Existing ADRs now lists all seven Approved ADRs (added ADR-005/006/007); the document's duplicate "## 12." section heading (colliding with §12 Dependencies) is corrected to "## 16."; §12 Dependencies and §15 References updated to cite ADR-005–007.
- **H3 — Section numbering corrected across eleven downstream volumes.** DS-003, DS-004, DS-005, DS-006, DS-007, DS-008, DS-009, DS-010, DS-011, DS-013, and DS-014 each had their Founder Vision Completion section renumbered from an arbitrary, out-of-sequence number to the correct next-available number in that document's own sequence. No section's content changed, only its heading number.
- **H4 — Stale pre-release archive removed.** `docs/codex.zip`, an untracked, undisclosed archive containing a complete pre-Foundation-Completion snapshot (56 files, all dated 2026-07-24, missing DS-RSH, DS-JRN, and ADR-005/006/007 entirely), has been deleted. No replacement zip-packaging workflow exists in this repository's publication tooling (`scripts/publication/docgen` generates per-document DOCX/PDF, not a raw Codex archive); none was fabricated to replace it.

## Blocker-Repair Pass (second addendum, 2026-07-25)

A second review returned six further High blockers against this release. All six are now repaired.

- **Blocker 1 — Publications regenerated.** All 14 DOCX and 14 PDF editions of DS-001 through DS-014 under `docs/publication/releases/` have been regenerated from the current, fully-repaired Markdown source via `scripts/publication/docgen/generate.py`. See the companion Validation Evidence for semantic-extraction confirmation and `docs/publication/PUBLICATION_MANIFEST.json` for updated checksums.
- **Blocker 2 — Trade Intelligence Package security authority added.** New `DS-SCA-029` (DS-008) establishes integrity, provenance, tamper-detection, authorization, no-unauthorized-deterministic-override, stale/partial-package protection, external-channel redaction, audit logging, conflicting-evidence handling, storage/transport protection, and fail-closed behavior for the canonical Trade Intelligence Package. Synchronized into DS-004 (`DS-ARC-028`), DS-005 (`DS-DB-028` constraints), DS-006 (`DS-API-TIP-001`'s full contract), DS-007 (`DS-UX-025` trust-state behavior), and DS-009 (new `DS-QA-027`).
- **Blocker 3 — Journal retention and deletion added.** New `DS-JRN-007` (DS-002) establishes user-controlled retention, deletion (including private/emotional content and attachments), propagation to derived reviews and Sage drafts, immutable-record preservation (Transaction/AuditLogEntry are never deleted), legal/audit-exception disclosure, export-before-delete, and privacy-safe deletion logging. Synchronized into DS-004 (`DS-ARC-027` extension), DS-005 (`DS-DB-032`/`DS-DB-033` constraints), DS-006 (new `DS-API-JRN-004`), DS-007 (`DS-UX-024` extension), DS-008 (`DS-SCA-028` extension), and DS-009 (new `DS-QA-028`).
- **Blocker 4 — DS-JRN-006 classification/roadmap corrected.** DS-011 §6a previously misrepresented `DS-JRN-006` (governing-classified Future/Exploratory in DS-002, and not Sage-dependent) as Planned and grouped it with `DS-JRN-005` under a Phase-6/Sage gate. Corrected so DS-JRN-006 carries no Planned classification and no phase placement anywhere in DS-011; DS-JRN-005 (genuinely Sage-dependent, Planned) is unaffected and no longer grouped with it.
- **Blocker 5 — API contracts completed.** `DS-API-RSH-001/002/003`, `DS-API-JRN-001/002/003`, and `DS-API-TIP-001` expanded from summary descriptions into full per-operation contracts (method, path, path/query params, headers, idempotency, request/response body schema with field constraints, success/validation/auth-failure/not-found/conflict/stale-data/integrity-failure/rate-limit/server-failure behavior, pagination, audit events, versioning/concurrency, redaction, paper/live restrictions), matching the rigor DS-006's own revision record already claimed. `DS-API-RSH-002` now has an explicit Acceptance Criteria block.
- **Blocker 6 — Release counts corrected.** The original H1 addendum above claimed 40 new traceability rows; the verified figure is 36. This blocker-repair pass adds 5 further new requirement IDs (`DS-JRN-007`, `DS-SCA-029`, `DS-API-JRN-004`, `DS-QA-027`, `DS-QA-028`) and 5 further traceability rows. **Final verified totals as of this addendum:** 23 new downstream IDs from the H1 pass + 5 new IDs from this blocker-repair pass = 28 new requirement IDs added across both repair passes; 36 traceability rows from the H1 pass + 5 from this pass = 41 net new traceability rows since the pre-repair baseline; current traceability matrix total: 184 rows, 184 unique controlled IDs, 0 duplicates; current Core release manifest entries: 46 (unchanged — no file added to or removed from the Core Codex's own file set by this pass; only existing entries' checksums changed).

See `RELEASE_MANIFEST_2026-07-25.json` for the updated file list and checksums, and `docs/publication/PUBLICATION_MANIFEST.json` for the regenerated publication artifacts' checksums.
