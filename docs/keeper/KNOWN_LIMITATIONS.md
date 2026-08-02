# Known Limitations

- Windows is the packaged and smoke-tested target; the standard-library code is
  portable, but macOS/Linux bundles are not produced.
- The final live protocol-6 smoke used a Founder-approved deterministic offline
  controlled provider. General authenticated Codex/Claude daily execution still
  requires its own supported Authority registration and qualification.
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
- An interrupted restore that leaves an Executive `ACTIVE` maintenance record
  intentionally blocks supported database access until the Founder runs
  exact-operation, integrity- and generation-checked recovery. An interrupted
  KeeperAuthority fence separately blocks covered project mutations until its bounded
  expiry and explicit operation-bound recovery; neither recovery path completes the
  restore automatically.
- The signed restore fence contains one project-scoped Authority snapshot and is
  bounded by the Authority protocol message limit. Extremely large personal-use
  attempt histories require a future paged signed-snapshot/fence protocol.
- This source requires KeeperAuthority 1.7.0, protocol 7, and schema 6. Application
  packaging never installs, restarts, updates, or reconfigures that service.
- The Codex subscription provider is authoring-only. Independent approval remains
  paused until a separately qualified reviewer provider is available.
- Provider Host lifecycle tooling is implemented and verified only against disposable
  roots in Phase 1. A Phase 2 migration must constrain the exact per-user install and
  Startup roots and connect lifecycle mutations to an authenticated Authority drain;
  the current disposable CLI roots and no-op drain callbacks are not production gates.
  Phase 1 nevertheless installs and verifies the complete manifest-bound standalone
  distribution and denies restricted-provider mutation of the disposable Startup
  namespace; it does not treat a lone executable as an installable package.
  Live installation, startup registration, enrollment, Authority
  migration, Codex registration/qualification, and model execution require a separate
  Phase 2 Founder authorization.
- Keeper 1.0 is a personal-use, single-Founder product. It does not claim to
  resist arbitrary code already executing in its trusted Executive interpreter,
  a malicious local administrator, manual same-user database replacement, or
  unsupported in-process plugins. Those are future service-isolation hardening
  scenarios, not supported-path release claims.
