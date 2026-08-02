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
- This source requires KeeperAuthority 1.7.1, protocol 7, and schema 6. Application
  packaging never installs, restarts, updates, or reconfigures that service.
- The Codex subscription provider is authoring-only. Independent approval remains
  paused until a separately qualified reviewer provider is available.
- Provider Host installation and enrollment are mechanically separate. Source
  1.7.1 adds the Founder-authenticated protocol-7 enrollment proposal/grant/proof/
  receipt/revocation lifecycle and permits an enrolled Host to start without a
  provider binding. Installation before the Authority upgrade remains inert and
  reports `INSTALLED_UNENROLLED`. Lifecycle verification uses disposable roots;
  the live Phase 2 migration must use the canonical per-user install and Startup
  roots plus the supported Authority lifecycle. The currently reviewed Host
  artifact is not Authenticode-signed, so enrollment binds the exact `NotSigned`
  status together with its immutable package manifest, executable SHA-256, file
  identity, canonical path, ACL, and non-exportable Host key; it does not invent a
  signer. A future signed artifact will instead require and bind the exact valid
  publisher certificate. Live installation, Authority migration/restart, Founder
  enrollment, Codex registration/qualification, and model execution remain
  separately authorized operations.
- Provider qualification uses a durable pre-bind `UNCERTAIN` fence and the
  supported exact `reconcile_provider_qualification` operation. This recovery
  surface is intentionally limited to the already validated registration and
  qualification evidence; it cannot substitute a provider, executable,
  account, model, or Host binding.
- Keeper 1.0 is a personal-use, single-Founder product. It does not claim to
  resist arbitrary code already executing in its trusted Executive interpreter,
  a malicious local administrator, manual same-user database replacement, or
  unsupported in-process plugins. Those are future service-isolation hardening
  scenarios, not supported-path release claims.
