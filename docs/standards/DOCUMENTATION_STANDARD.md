# DarkSage Documentation Standard
**Standard ID:** DS-DOC-STD-001
**Version:** 1.0.0
**Status:** Approved

## 1. Authority
Markdown is the engineering source of truth. Word/PDF editions are publication artifacts derived from approved source content.

## 2. Required Metadata
Every controlled document must identify: Document ID, title, version, status, owner, classification, repository, created date, last-updated date, and parent/related documents when applicable.

## 3. Status Lifecycle
Draft â†’ Under Review â†’ Approved â†’ Superseded/Deprecated.

- **Superseded:** replaced by a newer authoritative document or version.
- **Deprecated:** retained for historical or reference purposes but no longer recommended or current.

## 4. Versioning
Semantic versioning is used. Major = incompatible policy/structure change; Minor = approved expansion; Patch = correction/clarification.

## 5. Naming
Stable filenames omit status and version. Example: `DS-001-Executive-Vision.md`. Version/status live in metadata and Git history.

## 6. Requirement Language
Normative requirements use **shall**. Recommendations use **should**. Permissions use **may**. Requirements must be atomic, testable, traceable, and uniquely identified.

## 7. Traceability
Significant implementation work must map requirement â†’ design/ADR â†’ source â†’ test â†’ release/change record.

## 8. Review
Critical/High findings block approval. Approved requirements may not be silently changed.

## 9. Repository Neutrality
Repository-visible documentation must describe roles and processes without depending on a specific implementation assistant or review product.

This tool-neutrality rule applies to external development and review assistants. It does not prohibit the approved DarkSage product and project term **The DarkSage Codex**, or related documentation terms such as Codex-Driven Development, Codex Requirement, Codex Volume, and Codex Index.
