# Keeper Security

Keeper treats task definitions and process output as untrusted data.

- Paths are repository-relative, normalized, and checked for traversal.
- Changed files must match allowed paths and must not match blocked paths.
- Commands are argument arrays executed without a shell.
- Only commands in trusted task or workflow configuration are run.
- Freeform process output is never executed.
- Structured review output is schema-validated before use.
- Credential-like environment variables are filtered from child processes.
- Prompts and logs must not contain secrets.
- Dirty worktrees are never silently deleted.

Protected actions include force pushes, history rewrites, repository or backup
branch deletion, secret publication, purchases, paid resources, production
deployment, live trading, real trades, weakened security, disabled required tests,
and out-of-roadmap architecture changes. Keeper blocks these actions pending
explicit authorization.

The environment-name filter is defense in depth, not a secret manager. Operators
must use the repository's approved credential storage and inspect custom provider
configuration before execution.

## Local model assignment

`qwen2.5-coder:14b` is disabled for every role. `qwen3-coder:30b` is an approved
general-purpose provider for building, repair, review, tests, documentation,
analysis, exploration, and planning. It never reviews its own work. Every
Qwen-authored change passes normal verification and receives final review from a
different capable provider instance and context. High-risk changes require a
non-Qwen final reviewer. No Qwen model is an automatic fallback; if an approved
route is unavailable, the task becomes `BLOCKED`.
