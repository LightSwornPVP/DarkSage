# Authorization

Commit, push, network use, and worktree creation are separate capabilities. An
authorization records the exact repository/task scope, approving identity,
timezone-aware issue/expiry timestamps, reuse policy, revocation, and consumption.
Malformed, naive, expired, revoked, mismatched, or replayed authority fails closed.

Keeper never accepts authorization for merge, rebase, reset, stash, clean,
force-push, branch/worktree deletion, deployment, trading, or spending.
