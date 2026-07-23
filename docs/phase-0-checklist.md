# Phase 0 Checklist

Tracks the Phase 0 ("Foundation") exit criteria from `ROADMAP.md`. An item is only checked when it is verifiably true in the repository at the time this file was last updated — not when it is merely intended, configured-but-unconfirmed, or asserted.

- [x] Repository structure (`ai/`, `apps/`, `backend/`, `docs/`, `shared/`, `tests/` — each holds a `.gitkeep` placeholder so the empty directories survive a fresh clone; verified via `git ls-files`)
- [x] `PROJECT_SPEC.md`
- [x] `ARCHITECTURE.md`
- [x] `TRADING_RULES.md`
- [x] `SECURITY_RULES.md`
- [x] `AGENTS.md`
- [x] `ROADMAP.md`
- [x] `README.md`
- [x] `.gitignore`
- [x] Git/GitHub setup (origin: `LightSwornPVP/DarkSage`)
- [x] Development rules documented (`AGENTS.md` is the single authoritative, tool-neutral rulebook; any local development-tool configuration is machine-local and gitignored, never authoritative)
- [ ] Additional local development tooling setup (as needed — tool-neutral by design; not tracked here)
- [x] Branch and PR conventions (documented in `AGENTS.md`, templated in `.github/pull_request_template.md`)
- [x] CI foundation (`.github/workflows/ci.yml` exists and defines a secret-scan job and a foundation-checks job; whether these have actually run and passed on GitHub has not been confirmed from this development environment — no GitHub CLI access here)
- [x] Secret scanning foundation configured (`.github/workflows/ci.yml` gitleaks job); see `docs/secret-scanning.md` for the honest record of what has and has not actually been verified
- [x] VS Code setup (`.vscode/extensions.json`, `.editorconfig`, `.gitattributes`)

## Exit Criteria (from ROADMAP.md)

- [ ] Documentation committed — present and correct in the working tree/staged index, but no commit for this round of changes exists yet at the time this file was last updated. Do not check this box until the commit actually exists.
- [x] Directory structure, editor config, `.gitattributes`, and CI scaffold are in place and configured to be reproducible from a fresh clone
- [x] Repository rules are defined in `AGENTS.md` (single authoritative, tool-neutral document) — this records that the rules exist and are discoverable, not that every past change has been audited against them
- [ ] No secrets committed — **not fully verified**. A manual regex pass (common key patterns: `sk-`, `AKIA`, private-key headers, `ghp_`, Slack tokens) found no matches across the tracked tree, but no gitleaks binary, Docker, or GitHub CLI was available in this environment to run a real gitleaks scan or confirm the CI job has executed. See `docs/secret-scanning.md`.

## Next Up

Phase 1 — Core Market Intelligence (see `ROADMAP.md`). First slice: FastAPI skeleton, SQLite, Candle/Quote/Signal models, one provider adapter interface. Not started — plan separately before writing code.
