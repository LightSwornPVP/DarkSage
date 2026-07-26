# Troubleshooting

- Provider unavailable: configure its absolute executable path and rerun diagnostics.
- Git unsafe-directory error: approve the exact repository path; never add a global
  wildcard.
- Interrupted run: resume only at its persisted interrupted stage.
- Integrity error: preserve the data directory, restore a backup, or export readable
  records; do not overwrite evidence.
- Desktop does not open: run `python -m keeper.desktop --diagnostics`, then verify
  Tkinter is installed.
- Package failure: run `scripts/test-keeper-package.ps1` with the intended Python.
