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
without a display. Controlled command executables exercise complete workflows,
selected-stage retries, timeout/cancellation recovery, live redacted logging, and
restart-time retained-handle recovery. Adversarial coverage exercises post-validation
PID reuse, exited retained objects, parent and ownership changes, ambiguous
descendants, executable replacement, registration changes, truthful retry instance
IDs, actual-execution-only reporting, independent-connection authorization races,
and exact one-use reroute authority.

`python -m keeper.desktop --ui-smoke` creates actual Tk widgets and drives notebook
events, invokes the dashboard Refresh button, verifies the visible status update, and
writes structured evidence beneath the selected data directory when Tcl/Tk is
available. Exit code 78 with a JSON `unavailable` result means the Python runtime
lacks a usable Tcl/Tk installation; it is a skipped gate, not a pass.
