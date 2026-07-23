# Phase 0 Checklist

Tracks the Phase 0 ("Foundation") exit criteria from `ROADMAP.md`. Update this file as items are completed — do not mark an item done until it is actually true in the repo.

- [x] Repository structure (`ai/`, `apps/`, `backend/`, `docs/`, `shared/`, `tests/`)
- [x] `PROJECT_SPEC.md`
- [x] `ARCHITECTURE.md`
- [x] `TRADING_RULES.md`
- [x] `SECURITY_RULES.md`
- [x] `AGENTS.md`
- [x] `ROADMAP.md`
- [x] `README.md`
- [x] `.gitignore`
- [x] Git/GitHub setup (origin: `LightSwornPVP/DarkSage`)
- [x] Local development tooling configured (tool-neutral)
- [x] Branch and PR conventions (documented in `AGENTS.md`, templated in `.github/pull_request_template.md`)
- [x] CI foundation (`.github/workflows/ci.yml` — structural no-op until Phase 1 code exists)
- [x] Secret scanning foundation (`.github/workflows/ci.yml` gitleaks job)
- [x] VS Code setup (`.vscode/extensions.json`, `.editorconfig`)

## Exit Criteria (from ROADMAP.md)

- [x] Documentation committed
- [x] Development environment reproducible (git, editor config, CI scaffold in place)
- [x] Agents follow repository rules (`AGENTS.md`)
- [x] No secrets committed (verified by gitleaks CI job)

## Next Up

Phase 1 — Core Market Intelligence (see `ROADMAP.md`). First slice: FastAPI skeleton, SQLite, Candle/Quote/Signal models, one provider adapter interface. Not started — plan separately before writing code.
