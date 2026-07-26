# Testing

Run:

- `python -m pytest tests/keeper -q`
- `python -m pytest -q`
- `python -m mypy --strict keeper tests/keeper`
- `python -m compileall -q keeper tests/keeper`
- `git diff --check`
- `scripts/verify-foundation.sh` from Git Bash
- `powershell -File scripts/test-keeper-package.ps1`

Desktop behavior is tested through `KeeperViewModel` so tests remain headless.
Packaging smoke initializes fresh data, runs diagnostics and a complete mock pilot,
and exits cleanly.

Controller tests exercise first-run navigation and real application-service actions
without a display. Rendered Tk automation is unavailable in the current headless
environment and is not claimed.
