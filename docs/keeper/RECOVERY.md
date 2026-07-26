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
evidence path. A live process tree is terminated only when this identity matches.
A PID-only or inaccessible identity is classified as uncertain, remains blocked,
and is not terminated. A missing process may be eligible for an explicitly
authorized retry of the exact interrupted stage. Unfinished work is never
silently removed.

Inspect the recorded workspace and Git state before retrying a blocked task.
Keeper preserves dirty and failed worktrees. `cleanup-worktrees PATH` removes only
a clean registered worktree and refuses dirty work.
