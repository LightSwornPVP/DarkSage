# Authorization

Commit, push, network use, and worktree creation are separate capabilities. An
authorization records the exact repository/task scope, approving identity,
timezone-aware issue/expiry timestamps, reuse policy, revocation, and consumption.
Malformed, naive, expired, revoked, mismatched, or replayed authority fails closed.

Commit authority is bound to authorization ID, task, run, repository, worktree,
branch, HEAD, and exact staged paths. Push authority also binds the remote name and
URL, source and destination refs, expected commit, and non-force operation.

Keeper never accepts authorization for merge, rebase, reset, stash, clean,
force-push, branch/worktree deletion, deployment, trading, or spending.
