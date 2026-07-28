# Known Limitations

- Windows is the packaged and smoke-tested target; the standard-library code is
  portable, but macOS/Linux bundles are not produced.
- Authenticated Codex execution and Claude Code execution were not exercised during
  productization; their adapters are implemented but explicitly classified as such.
- OS toast delivery is best-effort; every notification is retained in-app.
- Discord remains a future notification-only adapter.
- Keeper does not automatically delete retained logs or evidence.
- The desktop provides structured textual evidence drill-down rather than an embedded
  side-by-side diff renderer.
- Authenticated external command-provider task execution remains unverified. Controlled
  executables exercise the complete production adapter and workflow path without
  external credentials.
- Startup recovery can terminate an exact owned Windows root through its retained
  native handle. It blocks if descendants exist or cannot be enumerated because a
  restarted process cannot safely recover the original job handle.
- The last staged-content revalidation and the Git commit operation are not one
  cross-process atomic transaction. Concurrent repository writers remain outside
  Keeper's trust boundary.
- Rendered Tk automation requires a Python runtime with matching Tcl/Tk libraries.
  The packaged diagnostic reports unavailable with exit 78 when that prerequisite is
  absent.
- Cross-process reroute reservation and storage races are covered directly. A
  dedicated separate-process test driving complete `WorkflowCoordinator.retry()`
  winner launch and loser exception handling remains deferred.
- An interrupted restore that leaves an `ACTIVE` maintenance record intentionally
  blocks supported database access until the Founder runs exact-operation,
  integrity- and generation-checked stale-maintenance recovery. There is no automatic
  lease expiry.
- The signed restore reconciliation is one project-scoped Authority response and is
  bounded by the Authority protocol message limit. Extremely large personal-use
  attempt histories require a future paged signed-snapshot protocol.
- Keeper 1.0 is a personal-use, single-Founder product. It does not claim to
  resist arbitrary code already executing in its trusted Executive interpreter,
  a malicious local administrator, manual same-user database replacement, or
  unsupported in-process plugins. Those are future service-isolation hardening
  scenarios, not supported-path release claims.
