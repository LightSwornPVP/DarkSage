# Pass B Recovery and Concurrency

## Launch protocol

Keeper creates a durable `Attempt` in `RESERVED` state before external launch.
It then transactionally acquires the launch claim and changes both attempt and
assignment to `LAUNCH_CLAIMED`. Only after that commit does it call the provider
adapter.

On restart:

- `RESERVED` attempts are classified `FAILED` before launch and may be
  re-prepared with a new attempt identity.
- `LAUNCH_CLAIMED` or `RUNNING` attempts become `UNCERTAIN`.
- uncertain assignments, workspace records, write records, and their normalized
  claims remain uncertain and reserved;
- active usage reservations remain preserved;
- uncertain work is not automatically retried or released.

Completion consumes the active usage reservation in the same SQLite
transaction that records completed attempt, evidence, and assignment state.
The partial unique launch index prevents a second active, completed, or
uncertain launch for the assignment.

## Usage reset

Insufficient capacity is not failure. The reservation transaction changes the
assignment to `WAITING_FOR_USAGE_RESET` and writes a `PauseReason` and
`ResumeCheckpoint`. The checkpoint binds project, charter revision, assignment,
workspace reservation, usage pool, authority-envelope digest, and checkpoint
state.

Resume requires the reset window to have passed and revalidates assignment
state, charter binding, authority digest, workspace ownership/state, and the
absence of an active or uncertain launch. The workspace is preserved while
waiting. There is no automatic paid fallback.

## Workspace concurrency

SQLite `BEGIN IMMEDIATE` transactions and normalized claim tables provide:

- one active writer for a canonical workspace path;
- overlapping protected-scope exclusion;
- concurrent reader allowance only through read-only reservations;
- owner-token lease renewal;
- explicit stale recovery after expiry;
- atomic propagation of renewal, release, stale, and uncertain state from a
  workspace to linked write records and claims.

Worktrees must be children of the configured implementation root. Protected
roots and `.ai-workflow/pw/` are rejected. Cleanup requires explicit approval,
terminal assignment state, preserved evidence, a clean worktree, and no
untracked files.

## Operator recovery rule

Never infer a safe retry from process loss alone. Inspect the control-room
uncertainty prompt, reconcile external provider and Authority truth, preserve
evidence, and make an explicit recovery decision.
