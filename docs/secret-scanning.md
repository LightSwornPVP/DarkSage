# Secret Scanning

## What CI Does

`.github/workflows/ci.yml` runs a `gitleaks` job (pinned to gitleaks v8.30.1 via `GITLEAKS_VERSION`) on every push and pull request against `main`.

- On a `push` event, it scans the commits included in that push.
- On a `pull_request` event, it scans the diff between the PR branch and its base.

`fetch-depth: 0` in the checkout step makes the full git history available to the action, but does not by itself guarantee gitleaks performs a full-history deep scan on every run — the scan scope follows the triggering event as described above. A green check means gitleaks found nothing in that event's scope. It does not mean every historical commit has been re-scanned in that run, and it does not mean a human has manually reviewed the diff — treat it as one layer, not the only layer. For a guaranteed full-history scan, run the local command below.

## Running gitleaks Locally

Install gitleaks (not required for this repo to function, only for local pre-push scanning). Pin a specific, reviewed version rather than installing whatever is newest at install time:

```bash
# via Go — pinned to the version this repo's CI also uses
go install github.com/gitleaks/gitleaks/v8@v8.30.1

# or download the v8.30.1 release binary from the gitleaks GitHub releases page
```

`detect` and `protect` were deprecated in gitleaks v8.19.0 (hidden from `--help`, though still present in some builds). Use the current commands instead.

Run a full-history scan of this git repository:

```bash
gitleaks git -v .
```

Scan the current working tree on disk (all files present, tracked or not — includes uncommitted and staged changes, but is not git-history-aware):

```bash
gitleaks dir -v .
```

## Verification Record

| Date | Method | Result | Limitations |
|---|---|---|---|
| 2026-07-22 | Manual regex pass over the tracked working tree (patterns: `sk-[A-Za-z0-9]{20,}`, `AKIA[0-9A-Z]{16}`, PEM private-key headers, `ghp_[A-Za-z0-9]{30,}`, Slack `xox[baprs]-` tokens) | No matches found | Not a substitute for gitleaks — narrower pattern set, no entropy analysis, no full git history walk. `gitleaks`, `docker`, and `gh` were all unavailable in the development environment this check was run from, so the CI gitleaks job's actual pass/fail history on GitHub has not been independently confirmed from this environment. |

Do not mark secret scanning as "verified" in `docs/phase-0-checklist.md` or elsewhere unless a real gitleaks run (local or via a confirmed CI job result) backs the claim, with the date and method recorded here.
