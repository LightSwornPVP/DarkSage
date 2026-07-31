# DarkSage Feature Status Definitions

| Field | Value |
|---|---|
| Document | Feature Status Definitions |
| Version | 0.1.0 |
| Status | Draft (Foundation Pass) |
| Owner | TheSinnerMan |
| Part of | Complete Features System (`docs/features/`), governed by DS-022 (`docs/codex/Volume-22-ProductExperience/`) |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

This document defines the controlled vocabularies used by `FEATURE_REGISTRY.csv` and the rest of the Complete Features System. It exists so a status, stage, or classification value means the same thing everywhere it is used — the same discipline the Core Codex's controlled-ID system already enforces for requirement IDs.

## 1. Implementation Status

Exactly one of the following, in `implementation_status`. **A later status in this list requires strictly more evidence than an earlier one; a feature can never claim a later status than its evidence fields support.**

| Status | Meaning | Minimum evidence required |
|---|---|---|
| **Idea** | Named and roughly scoped; not yet a committed requirement. | None. |
| **Future** | Explicitly deferred to a future stage; not a current commitment. | None, but must state a stage and groundwork classification. |
| **Planned** | A requirement exists (or is architected in this foundation pass) describing the feature, but no code has been written. | `design_evidence` pointing at a real requirement/architecture document. **Never treat Planned as implemented.** |
| **Designed** | Architecture/interface design exists beyond a bare requirement statement (e.g. a DS-ARC/DS-DB entry, or a skeleton volume section). | `design_evidence` pointing at the specific architectural artifact. |
| **In Development** | Code exists and is under active work but is not yet functionally complete. | `implementation_evidence` pointing at the actual source path(s). |
| **Implemented** | Code is functionally complete for its current scope. | `implementation_evidence` pointing at real source path(s). **Documentation alone is never sufficient — architectural documentation is not code completion.** |
| **Tested** | Implemented, and covered by automated tests that actually run in CI/locally. | `implementation_evidence` **and** `test_evidence` pointing at real test file(s). |
| **Released** | Tested, and shipped in an actual release artifact available to its intended audience (Founder build or a customer release channel). | `implementation_evidence`, `test_evidence`, **and** `release_evidence` (e.g. a release note, manifest entry, or version tag). |
| **Blocked** | Work cannot proceed because of a named, specific obstacle. | `blocker` field must name the specific obstacle (never "Blocked" with an empty or vague blocker). |
| **Deprecated** | No longer recommended; retained for reference/compatibility only. | `deprecation_notes` explaining why, **and** either `replacement_feature` or an explicit statement that no replacement exists. |
| **Removed** | No longer exists in any current build. | `deprecation_notes` documenting the removal and any migration path that existed. |

## 2. Release Stages

See `RELEASE_STAGE_MATRIX.csv` for the full per-stage definition (purpose, entry/exit criteria, platforms, editions, risks, timeline). The ten stages are: Stage 0 (Codex and Architecture) through Stage 9 (Marketplace, Global, and Institutional Expansion). **All stage timelines are nonbinding planning ranges, not commitments** — see `FEATURE_TIMELINE.md`.

## 3. Groundwork Classification (`groundwork_required_now` field)

| Value | Meaning |
|---|---|
| **Groundwork Required Now** | Architectural work must happen now (even though the feature itself ships later) or a later feature becomes materially harder or impossible without a rework. |
| **Can Be Added Later Without Current Architectural Work** | The feature can be designed and built entirely within its own future stage; nothing about today's architecture blocks it. |
| **Explicitly Rejected** | The capability conflicts with DarkSage safety or product direction and is not merely deferred — it is not planned at any future stage under current governance. |
| **Decision Pending** | Neither groundwork need nor rejection has been evaluated yet; an open decision, not a commitment either way. |

## 4. Safety Classification (`safety_classification` field)

| Value | Meaning |
|---|---|
| **Deterministic-Authoritative** | The feature is, or is gated by, the deterministic Risk Engine / TradeValidationPipeline. It can reject an action and nothing (no role, delegation, Sage recommendation, or remote control) may bypass that rejection. |
| **Advisory (Sage, non-authoritative)** | Sage may recommend, explain, or propose, but never approves, executes, or bypasses deterministic validation. |
| **Informational** | Presents information without exercising authority over trading decisions (e.g. a heatmap, a news feed). |
| **N/A** | Not applicable (e.g. a pure documentation/governance entry). |

## 5. Priority and Risk Level

`priority` (Critical / High / Medium / Low) reflects product importance. `risk_level` (Critical / High / Medium / Low) reflects the consequence of the feature being wrong, delayed, or defective — these are independent axes; a low-priority feature can still carry high risk (e.g. an experimental kill-switch variant).

## 6. Edition and Platform Values

- `edition_availability`: semicolon-separated subset of `{Founder, Customer}`, or `N/A` for a governance/documentation-only entry.
- `platform_availability`: semicolon-separated subset of `{Windows, macOS, Linux, Web, iOS, Android}`, or `N/A`.

## 7. Evidence Field Discipline

`design_evidence`, `implementation_evidence`, `test_evidence`, and `release_evidence` must each point at something real and checkable (a document, a source path, a test file, a release note) or state plainly "None" / "None — not released." **A fabricated or vague evidence citation is itself a governance defect** — this mirrors the Core Codex's own "never fabricate a checksum/value" discipline (see `scripts/publication/_repo.py`).

## Revision History

| Version | Date | Summary |
|---|---|---|
| 0.1.0 | 2026-07-25 | Initial foundation-pass definitions. |
