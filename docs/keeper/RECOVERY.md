# Keeper Recovery

## Executive database backup and restore

SQLite is the authoritative Executive persistence boundary. Normal writes commit
once inside SQLite; they do not require a subsequent adjacent lineage-journal
append. The retired schema-v7 lineage table and any preserved `.keeper-lineage`
artifact are legacy evidence only and are not read or advanced by normal
operation.

`KeeperStore.backup()` creates a complete SQLite snapshot at a unique temporary
path, runs SQLite and foreign-key integrity checks, and atomically replaces the
requested backup artifact. Backups are outside the live business transaction
path.

`KeeperStore.restore_backup()` is an explicit production maintenance API, never a
normal startup action. It accepts only an exact
`ProductionRestoreAuthorization`, an exact
`ProductionFounderAuthenticator`, and an exact
`ProductionAuthorityServiceClient`; arbitrary confirmation or reconciliation
callbacks are not accepted. The authorization binds the authenticated Founder SID,
restore operation ID, backup SHA-256 and recovery identity, target canonical path,
database ID, recovery epoch and write generation, complete project scope, reason,
issue time, expiry, and one-use consumption identity. Tests use a separate exact
test-only entry point and proof types.

The enforced sequence is:

1. Acquire the bounded OS-level exclusive database maintenance lock. Supported
   connections hold a shared lock for their full transaction, so a writer that
   already started must finish before restore can proceed and a new writer is
   rejected before it can commit.
2. Recheck the target database ID, recovery epoch, write generation, production
   mode, and authorization replay tables, then record an `ACTIVE` maintenance
   operation inside SQLite.
3. Stage, migrate, and integrity-check the exact authorized backup without changing
   live business state.
4. Request a KeeperAuthority-signed, project-scoped reconciliation receipt bound to
   the operation, backup, source and target recovery identities, generation, service
   key, protocol, and client SID. The receipt contains the complete current attempt
   and launch-authorization state, including completion, cancellation, and
   revocation.
5. Validate every Authority attempt against its restored Executive attempt and
   preserve one-time approval consumption and any budget reservation. A crossed
   launch boundary promotes a restored reservation to `CROSSED`; a newer terminal
   result is recorded as `UNCERTAIN` pending normal authenticated import, so it is
   represented but cannot cause a retry. Missing or conflicting Executive safety
   state rejects the restore.
6. Fetch and validate a second receipt immediately before replacement. Any changed
   Authority state, live generation, recovery identity, or maintenance lease aborts.
7. Pause every nonterminal project with
   `RESTORE_RECONCILIATION_REQUIRED`, consume the authorization, persist the signed
   receipt and Executive safety assessment, advance the recovery epoch and write
   generation, and populate `authority_reconciled_at` in the staged transaction.
8. Recheck the live boundary once more and replace the live database through the
   SQLite backup API while still holding the exclusive maintenance lock.

Validation, staging, integrity, Authority, or generation failure leaves the live
business state and recovery epoch unchanged. A handled failure records a failed
maintenance outcome and releases writers. Process termination after the durable
`ACTIVE` record leaves the database conservatively blocked.
`KeeperStore.recover_stale_restore(operation_id)` acquires the same exclusive lock,
requires the exact operation ID and unchanged write generation, verifies SQLite
integrity, and only then marks the interrupted lease failed; it never completes a
restore or changes business state.

The empty `.keeper-lock` file carries only an operating-system advisory byte lock;
it contains no state and is not a second database-plus-file commit protocol. Manual
same-user replacement of the database outside this workflow remains outside the
Keeper 1.0 personal-use threat model.

Pass A continues to support multiple normal Executive runtime writers through
SQLite transactions, CAS, uniqueness constraints, and the shared lock. Restore is
the enforced exclusive maintenance operation.

## Provider process recovery

An in-process paused desktop run persists `interrupted` and the exact prior stage,
and may resume only to that stage. The desktop coordinator inspects incomplete
runs during startup and records a durable recovery decision before allowing any
selected-stage retry.

Critical JSON state is written to a temporary file, flushed, and atomically
replaced. Each process run has its own directory under `.ai-workflow/runs/` with
the prompt, stdout, stderr, and `run.json`.

At startup, `start` and `resume` inspect incomplete runs. `recover` can be run
directly:

```bash
python -m keeper recover
```

Provider ownership records bind the PID to process creation time, executable,
command identity, parent, provider identity, run and stage, launch nonce, and
evidence path. On Windows, recovery opens one native process handle and retains it
from the first identity check through the destructive boundary. It reloads the
protected ownership record and provider evidence, rechecks the full live identity
through that same handle, and terminates only that exact process object through the
retained handle. Every path closes the handle.

Process discovery is tri-state. Only an operating-system-confirmed missing PID or
a signaled retained process object is treated as absent/exited. Access denial,
insufficient privilege, and unexpected query failures remain indeterminate,
blocked, and non-retry-safe. Protected ownership is never bypassed after an
indeterminate query.

Recovery never uses a PID-only tree kill after validation. Descendants cannot be
rebound to the original job after a restart, so a detected or unenumerable
descendant tree is classified as uncertain and left untouched. An inaccessible
handle, exited process, reused PID, identity change, ownership change, ambiguous
tree, or uncertain termination outcome also remains blocked and is not retry-safe.
A missing process may be eligible for an explicitly authorized retry of the exact
interrupted stage. Unfinished work is never silently removed.

A durable `EXECUTION_STARTED` provider attempt remains authoritative even when its
filesystem `run.json` is missing or unreadable. Provider evidence is corroborating
evidence only. Missing, malformed, duplicated, inaccessible, or identity-mismatched
evidence is recorded as indeterminate and is never retry-safe.

Recovery reads only the exact canonical `run.json` path protected in the durable
attempt. It does not search sibling provider directories for a matching run ID.
The path must remain canonical and contained in the run evidence root. The record
must exactly match the Keeper run, task, stage, role, attempt and retry parent,
logical provider and instance, stable registration, executable and configuration,
endpoint and authentication, capability and policy identities, evidence path,
launch nonce, and ownership token. Missing fields are mismatches, not wildcards.

Provider status is canonicalized and checked against explicit nonterminal and
terminal sets. Unknown or missing states and incomplete terminal dispositions
remain indeterminate. `RECOVERED_TERMINAL` additionally requires consistent
protected ownership and an authoritative result showing the exact process exited.

Mutable provider `run.json` terminal fields are never completion authority.
Normal completion writes an immutable Keeper completion record containing the
exact attempt identity, result, executable/configuration identity, and digest of
the provider evidence before finalizing protected attempt state. Recovery requires
that record (or the same trusted crash-gap journal), validates its integrity and
evidence digest, and only then permits `RECOVERED_TERMINAL`. If a child exits before
the protected record is persisted, the attempt remains uncertain and
non-retry-safe even when `run.json` claims success.

Before provider launch, Keeper durably creates a cryptographically random,
attempt-specific completion challenge. The completion journal binds that
challenge, process ownership, lifecycle transaction, and evidence digest and is
authenticated with the installation authority key. A manually inserted database
row, literal writer label, copied record, reused challenge, or correctly recomputed
public digest remains unverified without a valid writer proof.

Inspect the recorded workspace and Git state before retrying a blocked task.
Keeper preserves dirty and failed worktrees. `cleanup-worktrees PATH` removes only
a clean registered worktree and refuses dirty work.
