# DarkSage Feature Timeline

| Field | Value |
|---|---|
| Document | Feature Timeline |
| Version | 0.1.0 |
| Status | Draft (Foundation Pass) |
| Owner | TheSinnerMan |
| Part of | Complete Features System (`docs/features/`) |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

## Nonbinding Planning Disclaimer

**Every date range in this document, `RELEASE_STAGE_MATRIX.csv`, and the `tentative_start_window`/`tentative_completion_window` fields of `FEATURE_REGISTRY.csv` is a planning estimate, not a commitment.** Confidence levels are stated explicitly per stage/feature and should be read as literally as they are labeled — "Low" confidence means the range is a rough planning placeholder, not a schedule. No customer-facing communication should present these ranges as promised delivery dates.

## Stage Timeline (from current date, 2026-07-25)

| Stage | Estimated Duration Range | Confidence |
|---|---|---|
| Stage 0 — Codex and Architecture | 1–2 months remaining for expansion documentation | Medium |
| Stage 1 — Local Technical Foundation | 2–4 months | Medium |
| Stage 2 — Usable Paper-Trading Alpha | approximately 6–10 months total from current date | Medium |
| Stage 3 — Founder Workstation Beta | approximately 10–16 months total | Low |
| Stage 4 — Customer Cloud Beta | approximately 14–22 months total | Low |
| Stage 5 — Initial Commercial Release | approximately 18–30 months total | Low |
| Stage 6 — Advanced Trading Expansion | incremental delivery after initial release | Low |
| Stage 7 — Platform and TradingView-Style Expansion | approximately years 2–4 | Low |
| Stage 8 — Strategy Ecosystem and Private Collaboration | approximately years 3–5 | Low |
| Stage 9 — Marketplace, Global, and Institutional Expansion | long-range, approximately year 5+ | Low |

See `RELEASE_STAGE_MATRIX.csv` for each stage's full purpose, entry/exit criteria, dependencies, primary platforms/editions, and major risks.

## Why Confidence Degrades Over the Horizon

Stage 0–2 estimates are Medium confidence because they build directly on work already substantially underway (market data, indicators, backtesting, and scanner modules already have real implementation and test evidence — see `tests/test_market_data_*.py`, `tests/test_indicator_*.py`, `tests/test_backtest_*.py`, `tests/test_scanner*.py`). Stage 3 onward is Low confidence because it depends on architecture (edition boundary, cloud migration, multi-account, commercialization) that exists today only as a Draft skeleton (DS-015–DS-023), not yet a reviewed, approved design.

## Founder Sage Developer Mode (`FEAT-0268`)

Groundwork begins in Stage 1 (Local Technical Foundation); a usable private version is targeted for Stage 3 (Founder Workstation Beta), alongside Founder Local Sage and Founder-only Python research extensions. It is Founder-only and carries no customer-facing timeline commitment at any stage.

## How to Read Per-Feature Timeline Fields

Each `FEATURE_REGISTRY.csv` row's `tentative_start_window`/`tentative_completion_window`/`timeline_confidence` are independent of the stage-level table above where a feature's own blocker or dependency chain places it earlier or later than its nominal stage would suggest (e.g. a feature blocked on an external decision carries `blocker` text explaining the actual constraint, not just a stage label).

## Revision History

| Version | Date | Summary |
|---|---|---|
| 0.1.0 | 2026-07-25 | Initial foundation-pass timeline, matching the planning model specified in the Product Expansion foundation instructions. |
