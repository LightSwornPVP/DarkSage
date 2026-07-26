# Keeper Recovery

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

Inspect the recorded workspace and Git state before retrying a blocked task.
Keeper preserves dirty and failed worktrees. `cleanup-worktrees PATH` removes only
a clean registered worktree and refuses dirty work.
