# Keeper Recovery

An in-process paused desktop run persists `interrupted` and the exact prior stage,
and may resume only to that stage. Restart recovery after provider execution is not
yet integrated with the desktop coordinator; preserve its database, evidence, and
worktree for review rather than starting an automatic replacement.

Critical JSON state is written to a temporary file, flushed, and atomically
replaced. Each process run has its own directory under `.ai-workflow/runs/` with
the prompt, stdout, stderr, and `run.json`.

At startup, `start` and `resume` inspect incomplete runs. `recover` can be run
directly:

```bash
python -m keeper recover
```

When a recorded process is no longer alive, its run is marked `interrupted` with
an exact reason. Live processes are left untouched. Recovery decisions are saved
in `.ai-workflow/recovery-state.json`; unfinished work is never silently removed.

Inspect the recorded workspace and Git state before retrying a blocked task.
Keeper preserves dirty and failed worktrees. `cleanup-worktrees PATH` removes only
a clean registered worktree and refuses dirty work.
