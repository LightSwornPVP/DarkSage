# DarkSage Naming & Identifier Standard

**Version:** 1.1.0
**Status:** Approved
**Last Updated:** 2026-07-25

## Controlled Documents
`DS-001`, `DS-002`, etc.

## Requirements
`DS-<DOMAIN>-NNN`, e.g. `DS-RSK-014`.

## Architecture Decisions
`ADR-NNN`.

## Change Proposals
`DSCP-NNN`.

## Design Reviews
`DR-NNN`.

## Flagship Publication Documents

`DSF-NNN` — DarkSage Flagship Publication Document.

**Purpose:** Reserved for:
- the flagship publication architecture;
- derived executive/product/requirements publication documents (e.g., an Executive Product Plan, a consolidated Product Requirements Specification);
- publication manifests or other controlled publication documents, where explicitly approved.

**Authority boundary:**
- Publication-only. A `DSF-NNN` document governs publication architecture, publication workflow, visual and layout rules, and its own derived-summary wording — nothing more.
- Not a product requirement family. A `DSF-NNN` document does not create, and is never cited as the Governing Source for, a `DS-<DOMAIN>-NNN` requirement.
- Does not supersede Codex or root governance. For all product, engineering, safety, security, lifecycle, Release Classification, and architecture meaning, the controlling Codex (`DS-NNN`, `ADR-NNN`) and root public governance documents (`SECURITY_RULES.md`, `TRADING_RULES.md`, `ARCHITECTURE.md`, `PROJECT_SPEC.md`, `ROADMAP.md`, `AGENTS.md`) remain the sole authority.
- Cannot establish product classification, implementation commitment, or architecture authority independently. A `DSF-NNN` document may summarize or consolidate such content for publication purposes, but never originates it.

**Lifecycle:** A `DSF-NNN` document follows the same controlled-document version/status/revision-history requirements as any other controlled document — Status lifecycle Draft → Under Review → Approved → Superseded/Deprecated; semantic versioning per `docs/standards/DOCUMENTATION_STANDARD.md` §4.

**Uniqueness:** `DSF-NNN` identifiers are repository-wide unique, the same as every other controlled-ID namespace in this standard.

**Examples:**
- `DSF-001` — DarkSage Flagship Publication Architecture
- `DSF-002` — DarkSage Product Requirements Specification

## File Naming
Use stable kebab-case names:
`DS-001-Executive-Vision.md`

Do not place mutable version/status text in controlled filenames.

## Revision History

| Version | Date | Summary |
|---|---|---|
| 1.0.0 | (unversioned baseline) | Original naming standard: `DS-NNN`, `DS-<DOMAIN>-NNN`, `ADR-NNN`, `DSCP-NNN`, `DR-NNN`, and file-naming rules. No version marker was recorded on this document prior to 1.1.0; this entry records the pre-existing baseline content for traceability rather than asserting a specific prior date. |
| 1.1.0 | 2026-07-25 | Added `DSF-NNN` (DarkSage Flagship Publication Document) as an authorized, repository-wide-unique controlled-document-ID namespace with an explicit publication-only authority boundary, per targeted repair FLAG-H02 (independent audit of `DSF-001`/`DSF-002`). No existing namespace, ID, or file-naming rule was changed. |
