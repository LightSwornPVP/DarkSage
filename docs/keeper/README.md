# Keeper

Keeper is a local-first desktop control center for fail-closed software-development
workflows. It manages repositories, tasks, provider diagnostics, scoped
authorizations, independent review, repair, verification, evidence, and reports.

Launch development mode with `powershell -File scripts/keeper-desktop.ps1`, or build
the single-file Python application described in `PACKAGING_RELEASE.md`. The built-in
deterministic mock provider makes setup and demonstrations possible without network
access or external credentials.

Keeper never grants itself authority to merge, rewrite history, force-push, deploy,
trade, spend money, or delete repositories, branches, or worktrees.
