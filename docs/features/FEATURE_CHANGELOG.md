# DarkSage Feature Changelog

| Field | Value |
|---|---|
| Document | Feature Changelog |
| Version | 0.1.0 |
| Status | Draft (Foundation Pass) |
| Owner | TheSinnerMan |
| Part of | Complete Features System (`docs/features/`) |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

Records every material change to the Complete Features System: new features added, status changes, stage reassignments, deprecations, and governance amendments. This is distinct from `docs/codex/RELEASE_NOTES_*` (which records Core Codex changes) — this changelog is scoped to the feature registry and its governance only.

## 2026-07-25 — Foundation Pass (Initial Creation)

- Created the Complete Features System from scratch: `DARKSAGE_COMPLETE_FEATURES.md`, `FEATURE_REGISTRY.csv` (267 features across 32 categories), `FEATURE_DEPENDENCIES.csv` (46 dependency edges), `RELEASE_STAGE_MATRIX.csv` (10 stages, Stage 0–9), `PLATFORM_CAPABILITY_MATRIX.csv`, `EDITION_CAPABILITY_MATRIX.csv`, `FEATURE_TIMELINE.md`, `FEATURE_STATUS_DEFINITIONS.md`, `FEATURE_GOVERNANCE.md` (including the controlled-ID family collision analysis), and `TRADINGVIEW_CAPABILITY_COMPARISON.md`.
- Created nine new Product Expansion Codex volumes (DS-015 through DS-023) as structural skeletons — no full requirement drafting yet.
- No DS-001–DS-014 requirement, classification, or count was altered. The Core Codex remains locked at commit `1e48041fb59593b3bc62c490e3bb60d343287a15`.
- Recorded one deferred Medium-severity cleanup item (20 Planned compound `DS-API-*` requirements missing individual rows in `TRACEABILITY_MATRIX.csv`) — explicitly not addressed in this pass, per instruction.
- Initial feature-status distribution: predominantly Idea/Planned, with a small number of Implemented/Tested entries backed by real evidence (market data, indicators, backtesting, scanner, database — see `tests/` for the corresponding test files). No feature is marked Released; nothing in this expansion has shipped yet.

## 2026-07-26 — Independent-Audit Repair Pass

- Corrected unsupported `Implemented` claims for FEAT-0003/FEAT-0139/FEAT-0140 to `Designed` (no live TradeValidationPipeline/Risk Engine code exists yet; the prior claim cited backtesting-simulation code that explicitly disclaims being the real execution path). No other Implemented/Tested/Designed/In Development/Deprecated/Blocked row required a status change on review.
- Resolved all 11 `initial_release_required = Yes` + `Idea` features: 10 reclassified to `Planned` with a documented reason; 1 (FEAT-0201, Bracket visualization) reclassified `initial_release_required = No`, moved to Stage 6.
- Made `FEATURE_DEPENDENCIES.csv` canonical for dependency edges; the registry's own `dependencies` column is now a generated, always-synchronized summary of that file (46 edges).
- Replaced all 249 self-referential (`"This registry entry"`) `design_evidence` values with real citations or `Not Yet Designed`; replaced all placeholder `acceptance_summary` values for safety-critical/initial-release/committed features (169 rows) with concrete, testable criteria. Distant Idea/Future backlog may still carry a placeholder under the new governance permission (`FEATURE_GOVERNANCE.md` §3a).
- Repaired all 37 stop-loss/take-profit features: added DS-023 dependencies for order-lifecycle/reconciliation/failure-handling rows and DS-016/DS-022 for mobile/chart-interaction rows; confirmed no true semantic duplicates among the 37.
- Resolved DS-SCR vs. DS-SCN (both DS-002-owned, distinct scope, no overlap) and permanent ownership for DS-DRW/DS-WCH/DS-VIZ/DS-CAL/DS-ECO (reassigned from DS-022 to DS-002 where content is normative business behavior, not UX).
- Reconciled all TradingView capabilities against registry stage/initial-release/groundwork values; corrected 10 misclassifications (including the previously-empty B classification); new totals A=27 B=5 C=57 D=52 E=2.
- Corrected Founder Local Sage / Founder-only Python research extensions / Founder-asset extraction resistance platform assignments (no longer represented as Web/iOS/Android-available).
- Added **Founder Sage Developer Mode** (`FEAT-0268`, category 33; owner DS-018, supporting DS-015/DS-021/DS-023) — Founder-only, private, local-workstation coding/research assistant. 268 features total (was 267); does not change the Core Codex's 459/493 controlled-ID totals.
- Rewrote `validate_feature_registry.py` to fail closed (27 checks) and added a 30-test regression suite (`tests/test_validate_feature_registry.py`), all passing.

## Revision History

| Version | Date | Summary |
|---|---|---|
| 0.1.0 | 2026-07-25 | Initial changelog entry documenting the foundation pass. |
| 0.2.0 | 2026-07-26 | Independent-audit repair pass (see above). |
