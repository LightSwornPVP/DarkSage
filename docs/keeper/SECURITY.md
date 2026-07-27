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
- Final evidence is indexed by path, byte count, and digest, then its
  security-relevant report fields and provider-attempt identities are copied into
  an immutable finalization record. Export revalidates both layers.

Protected actions include force pushes, history rewrites, repository or backup
branch deletion, secret publication, purchases, paid resources, production
deployment, live trading, real trades, weakened security, disabled required tests,
and out-of-roadmap architecture changes. Keeper blocks these actions pending
explicit authorization.

The environment-name filter is defense in depth, not a secret manager. Operators
must use the repository's approved credential storage and inspect custom provider
configuration before execution.

## Authenticated lifecycle authority

Keeper creates a 256-bit installation authority key with the operating system
cryptographic random source. On Windows the stored key blob is protected with
current-user DPAPI and kept under the Keeper data directory's dedicated
`authority/` folder, outside repositories, worktrees, provider evidence, and
qualification working directories. On non-Windows systems the key file must have
mode `0600`; broader permissions fail closed. The plaintext key exists only in the
trusted Keeper process. On Windows, Keeper also retains a non-inheritable,
exclusive read handle on the protected blob for each provider-execution window,
so the launched provider cannot reopen it. A concurrent launch fails closed
instead of sharing the key file.

The key is never placed in configuration, environment variables, command lines,
stdin, logs, reports, or provider working directories. Provider children receive
only public challenges and evidence paths. Qualification and completion records
carry a versioned key identifier and HMAC-SHA-256 writer proof over their complete
canonical payload. Verification uses constant-time comparison. Public SHA-256
digests remain useful for content reconciliation but never establish writer
authority.

Key loading, DPAPI unprotection, identifier mismatch, or authentication failure
blocks qualification and completion. There is no unkeyed fallback. Automatic key
rotation is intentionally disabled for the MVP. Rotation requires retaining the
old DPAPI-protected key for records that must remain verifiable; deleting or
replacing it makes old records unverifiable and therefore non-retry-safe.

Commit authorization and mutation are separate operating-system and Git
operations. Keeper revalidates the authorized staged-content digest immediately
before commit, but no cross-process transaction can make the final check and Git
mutation atomic. Operators must prevent concurrent writers during an authorized
commit.

## Local model assignment

`qwen2.5-coder:14b` is disabled for every role. `qwen3-coder:30b` is an approved
general-purpose provider for building, repair, review, tests, documentation,
analysis, exploration, and planning. It never reviews its own work. Every
Qwen-authored change passes normal verification and receives final review from a
different capable provider instance and context. High-risk changes require a
non-Qwen final reviewer. No Qwen model is an automatic fallback; if an approved
route is unavailable, the task becomes `BLOCKED`.
