# Keeper

Keeper is a local-first desktop control center for fail-closed software-development
workflows. It manages repositories, tasks, provider diagnostics, scoped
authorizations, independent review, repair, verification, evidence, and reports.

Desktop-created tasks now enter the authoritative persisted lifecycle and the same
orchestration engine used by provider workflows. The deterministic acceptance route
supports repair, no-repair, blocked-reviewer, manual approval, rejection,
pause/resume, cancellation, and report finalization.

Launch development mode with `powershell -File scripts/keeper-desktop.ps1`, or build
the single-file Python application described in `PACKAGING_RELEASE.md`. The built-in
deterministic mock provider makes setup and demonstrations possible without network
access or external credentials.

Keeper never grants itself authority to merge, rewrite history, force-push, deploy,
trade, spend money, or delete repositories, branches, or worktrees.

Keeper 1.0 release audits use the controlled personal-use boundary in
[`THREAT_MODEL.md`](THREAT_MODEL.md). Provider output remains untrusted and is
never loaded as code into the trusted Executive interpreter.
