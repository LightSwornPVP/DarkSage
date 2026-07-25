# DarkSage Next Implementation Slice

| Field | Value |
|---|---|
| Document ID | DEV-SLICE-001 |
| Version | 1.2.0 |
| Status | Proposed — not implemented |
| Baseline | `34a65818d48f596122281075e18c6e5f36ec93b5` (see [[DARKSAGE_IMPLEMENTATION_STATE]]) |

This document selects and specifies the smallest valuable next coding slice. **It is a plan only — no implementation code is included in this pass.**

## Objective

Persist backtest performance results so they survive process restarts and can be queried/compared over time, instead of living only in the in-process `ExperimentRegistry` (`backend/app/backtesting/comparison.py`). This is the first real use of the database layer (currently zero ORM models, zero migrations — see implementation-state §2/§3) and is the literal first bullet of ROADMAP Phase 3 ("Strategy performance database"). Confirmed against DS-DB-006 and DS-API-COR-004/005 (see revision history) to remain the smallest valuable next slice: persistence-only, with no new HTTP endpoint, is smaller than a version that also stands up authentication infrastructure just to expose one.

## Controlling requirement IDs

- `DS-PERF-001` — Performance Metric Tracking (`docs/codex/Volume-02-Product/requirements/DS-PERF-Strategy-Performance.md`) — governing purpose and metric list
- `DS-BKT-001` — dependency (backtesting engine; already implemented, Phase 2)
- `DS-DB-005` — **StrategyProfile** Phase-1 core (`docs/codex/Volume-05-Database/DS-005-Database-Design.md`), Committed/MVP — required persistence prerequisite for DS-DB-006's version-pinned foreign key
- `DS-DB-006` — **BacktestResult** (`docs/codex/Volume-05-Database/DS-005-Database-Design.md`), Planned — the controlling persistence contract this slice must match exactly (see Data-model impact)
- `DS-API-COR-004` — Authentication and Authorization (`docs/codex/Volume-06-API/DS-006-API-Specification.md`), Committed/MVP obligation — governs why this slice exposes no new HTTP endpoint (see In scope / Out of scope)
- `DS-API-COR-005` — Pagination and Filtering (same volume), Committed/MVP obligation — same reason
- `ROADMAP.md` Phase 3 — "Strategy performance database" (first listed item)
- `ADR-003` — Deterministic Financial Calculations (constrains storage of `Decimal`-typed metric fields)

## In scope

- First SQLAlchemy ORM models under `backend/app/database/models/`: the committed Phase-1 core of **DS-DB-005 StrategyProfile**, followed by **DS-DB-006 BacktestResult** (see Data-model impact). StrategyProfile is included only because BacktestResult cannot truthfully implement DS-DB-006's required version-pinned foreign key without its referenced table.
- First Alembic migration (`backend/alembic/versions/`) creating both tables in dependency order.
- A repository/service function to persist one backtest run's result (`ExperimentEntry`/`PerformanceMetrics` from `backend/app/backtesting/comparison.py`/`metrics.py`) into the DS-DB-006 shape after a backtest completes.
- Unit tests for the new model, migration, and repository function.

## Out of scope

- **Any new HTTP API endpoint.** The prior version of this slice proposed `GET /backtests` and `GET /backtests/{run_id}` and described them as "unauthenticated... consistent with current app-wide state" — that reasoning was wrong: `DS-API-COR-004` (Authentication and Authorization) and `DS-API-COR-005` (Pagination and Filtering) are both Committed/MVP obligations on every non-public, list-returning endpoint, and `/health`/`/ready` are liveness probes, not a precedent for data endpoints. Since no authentication infrastructure exists anywhere in the app yet (implementation-state §4) and standing one up is materially larger than "the smallest valuable next slice," this version persists results through an internal repository function only, verified by direct unit tests — no endpoint, so no auth/pagination obligation is incurred or violated. Exposing a read endpoint is deferred to a later slice, once authentication exists.
- Strategy × sector/timeframe/regime analysis, entry/exit-method analysis, Strategy DNA, regime classification, strategy ranking (later Phase 3 items — this slice only lands the persistence foundation they'll build on).
- Any change to the backtesting engine, metrics computation, or `ExperimentRegistry` itself — this slice only adds a persistence path alongside the existing in-memory registry.
- Postgres migration (SQLite remains the target per current `Settings.database_url` validation; the "Postgres migration trigger" open question in `.ai-workflow/BLOCKERS.md` is unrelated and unresolved by this slice).
- `MarketRegime`/`regime_id` population — DS-DB-006 defines `regime_id` as a nullable FK to a regime-classification table that does not exist yet (later Phase 3 item); this slice's schema includes the nullable column per the contract but never populates it.

## Expected files/modules

- New: `backend/app/database/models/strategy_profile.py` — SQLAlchemy `StrategyProfile` ORM model limited to DS-DB-005's committed Phase-1 core fields (`strategy_id`, `name`, `version`, `status`, `created_at`, `superseded_by`).
- New: `backend/app/database/models/backtest_result.py` — SQLAlchemy `BacktestResult` ORM model matching DS-DB-006's field list exactly.
- New: `backend/alembic/versions/0001_create_strategy_profiles_and_backtest_results.py` (first migration; creates the referenced StrategyProfile table before BacktestResult).
- New: `backend/app/backtesting/persistence.py` — repository function bridging `ExperimentEntry`/`PerformanceMetrics` → the `BacktestResult` row shape.
- New: `tests/test_backtest_persistence.py`.
- No change to `backend/app/main.py` or any router — no endpoint is added in this slice.

## Data-model impact

First real tables in the schema. The prerequisite `strategy_profiles` table is limited to **DS-DB-005's committed Phase-1 core** (`strategy_id`, `name`, `version`, `status`, `created_at`, `superseded_by`) and enforces version-row identity plus the nullable self-referential supersession chain. The `backtest_results` table then matches **DS-DB-006's actual field list** (not a column-per-metric approximation):

- `backtest_id` — primary identifier
- `strategy_id` — FK, **version-pinned** (references the exact `StrategyProfile` version used, per DS-DB-006's Key Relationships — never a mutable reference to "current" strategy state, so a later strategy edit cannot retroactively reinterpret a past result)
- `date_range_start`, `date_range_end`
- `cost_assumptions` — JSON (per DS-BKT-002's cost-assumption disclosure requirement)
- `data_snapshot_reference` — identifies the exact historical data snapshot used, for reproducibility
- `results` — JSON, containing `trade_count`, `win_rate`, `expectancy`, `profit_factor`, `max_drawdown`, `sharpe`, `sortino`, `sample_size_confidence` (DS-DB-006's own field list) plus the remaining `PerformanceMetrics` fields not named there (`cagr`, `average_win`, `average_loss`, `win_loss_ratio`, `max_drawdown_duration`, `volatility`, `exposure`, `average_holding_time`, `best_trade_pnl`, `worst_trade_pnl`, `average_r_multiple`) — stored as JSON per the contract's own shape, with `Decimal`/`timedelta` values serialized losslessly (string-encoded, never coerced to `float`, per `ADR-003`)
- `regime_id` — FK, nullable (see Out of scope)
- `executed_at`

**Immutable once written** (DS-DB-006's own constraint, from DS-BKT-001's reproducibility requirement): no update path is implemented for an existing row; a corrected re-run creates a new `backtest_id`, never an in-place edit.

## API impact

None — no new endpoint in this slice (see Out of scope).

## UI impact

None — no frontend exists (see implementation-state §4).

## Security impact

None: no new endpoint, no execution/trading/broker/risk logic touched, no new external network calls, no secrets/credentials involved. Removing the previously-proposed unauthenticated endpoint is itself the security-relevant correction in this revision.

## Acceptance criteria

1. A backtest run's result can be persisted and re-read as a `BacktestResult` row with all fields — including the `results` JSON blob's `Decimal`/`timedelta` values — value-identical to the source `PerformanceMetrics`.
2. `alembic upgrade head` from an empty database creates both tables and their foreign keys with no errors; `alembic downgrade` cleanly drops both.
3. Attempting to persist a second result against the same `backtest_id` is rejected (immutability).
4. Persisting a result whose `strategy_id` does not resolve to an existing, version-pinned `StrategyProfile` is rejected (fail closed, no orphaned row).
5. Persisting a result with a missing/invalid `data_snapshot_reference` or malformed `results` payload is rejected before any row is written.
6. All new code passes `mypy backend shared ai` and the existing test suite continues to pass unmodified.

## Tests

- Model round-trip test (write a `BacktestResult` row, read it back, assert equality including `Decimal`/`timedelta` fields inside `results`).
- StrategyProfile prerequisite test: persist two version rows for one strategy and verify the DS-DB-005 identity/versioning chain and nullable `superseded_by` relationship.
- Migration test: apply migration to a throwaway SQLite DB, assert both expected tables/columns and the BacktestResult → StrategyProfile foreign key exist; apply `downgrade()` and assert both tables are gone (rollback behavior).
- Immutability test: a second write attempt against the same `backtest_id` is rejected.
- Invalid-input tests: missing/unresolvable `strategy_id` version, missing `data_snapshot_reference`, malformed `results` structure — each rejected before persistence.
- Audit-field test: `executed_at` and `cost_assumptions` are always present and never null on a successfully persisted row.
- Repository function unit test using an in-memory/temp SQLite session.

## Failure behavior

- Persistence failure (e.g. DB unavailable, validation failure) must not crash or corrupt an in-progress backtest run — the repository function raises a clear, typed exception; the caller decides whether to fail the run or log-and-continue. Fail closed: never silently drop a result while reporting success.
- An attempted overwrite of an existing `backtest_id` fails loudly (typed exception), never a silent no-op or silent overwrite.

## Migration requirements

One new Alembic migration only (`0001_...`), additive (`CREATE TABLE strategy_profiles`, then `CREATE TABLE backtest_results`), no data migration needed since no prior data exists. It must be reversible in dependency-safe reverse order — verified by an explicit upgrade/downgrade round-trip test, not merely asserted.

## Dependencies and honest gaps

- The repository currently has a frozen Pydantic `shared.models.StrategyProfile` but **no persisted StrategyProfile table**. DS-DB-006 requires `strategy_id` to be a version-pinned foreign key, so this slice explicitly implements DS-DB-005's committed Phase-1 ORM core as a prerequisite in the same migration; it does not pretend the Pydantic model can satisfy a database FK.
- Beyond that explicitly included persistence prerequisite, the slice does not depend on authentication, an API router, pagination conventions, MarketRegime persistence, or other unimplemented infrastructure.
- **Explicitly does not resolve**: the API-layer read path is still needed eventually (tracked as a follow-on slice, gated on `DS-API-COR-004` authentication existing first) and the open cross-cutting API decisions (auth mechanism, pagination style) remain unresolved per DS-006 Appendix A — this slice does not silently depend on either being resolved, and does not attempt to resolve them itself.

## Audit checklist

- [ ] No `Decimal` value silently coerced to `float` anywhere in the persistence path (`ADR-003`)
- [ ] No naive datetime written without timezone normalization (`executed_at` and any timestamp inside `results` must be timezone-aware; per `ADR-003`'s determinism requirement — no untracked local file is cited as authority for this rule)
- [ ] No HTTP endpoint added in this slice; if a future slice adds one, it must satisfy `DS-API-COR-004` and `DS-API-COR-005` before merging, not after
- [ ] `strategy_id` is version-pinned, never a mutable "current strategy" reference
- [ ] `BacktestResult` rows are immutable once written — no update path exists
- [ ] Migration is additive and reversible (upgrade/downgrade round-trip tested)
- [ ] New tests actually fail without the implementation (verified before merge)
- [ ] `mypy backend shared ai` and full test suite pass

## Commit plan

Single phase-numbered slice, following the existing `1.x`/`2.x` convention — this would be the first commit of Phase 3, i.e. `3.1`, `3.2`, ... (model + migration, then repository function + tests). Not created in this pass.

## Revision History

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-07-25 | Initial slice proposal. |
| 1.1.0 | 2026-07-25 | Targeted High-finding repair (H5): removed the proposed `GET /backtests`/`GET /backtests/{run_id}` HTTP endpoints entirely rather than describing them as security-neutral — they conflicted with `DS-API-COR-004` (Committed/MVP authentication obligation) and `DS-API-COR-005` (Committed/MVP pagination obligation), neither of which this slice's persistence-only scope can or should satisfy. Replaced the column-per-metric `Data-model impact` with DS-DB-006's actual `BacktestResult` contract (JSON `results`/`cost_assumptions`, `data_snapshot_reference`, version-pinned `strategy_id`, nullable `regime_id`, immutability). Removed the untracked `LOCAL_CODER_RULES.md` as a cited acceptance authority (git status shows it untracked at this baseline) in favor of `ADR-003`. Added acceptance criteria/tests for immutability, invalid input, and migration rollback. |
| 1.2.0 | 2026-07-25 | Focused final-verification repair (H5): made the missing DS-DB-005 persistence prerequisite explicit. The repository has only a Pydantic `StrategyProfile`, not an ORM table, so DS-DB-006's required version-pinned foreign key was not implementable by the 1.1.0 file/migration plan. Added the DS-DB-005 Phase-1 core ORM model, dependency-ordered creation in the same first migration, and foreign-key/version-chain tests; no endpoint or broader Strategy Intelligence scope was added. |
