# Changelog

## 0.5.5

- Separate provider registration from protected qualification; version metadata
  now comes only from an authorized retained-component qualification launch and
  immutable qualification evidence.
- Preserve registered capability and role restrictions through diagnostics,
  selection, routing evidence, and reports.
- Require an immutable Keeper completion journal before recovery can accept
  mutable provider evidence as terminal.
- Align standalone batch startup with qualified launcher/script composite
  registrations.

## 0.5.4

- Resolve recovery evidence only from the protected canonical `run.json` path
  and require complete execution identity plus an explicit provider status.
- Canonically digest the complete schema-versioned provider registration,
  including qualification and authorization metadata.
- Align standalone command startup with the current registration schema and
  exact invocation binding used by desktop routing.

## 0.5.3

- Require protected, pre-existing provider registration before command-provider
  discovery can report a provider as available.
- Preserve authoritative Windows launcher and batch-script component identities
  through adapter construction and launch evidence.
- Treat every unresolved durable execution-started attempt as indeterminate and
  non-retry-safe when provider evidence is missing, malformed, duplicated, or
  inconsistent.

## 0.5.2

- Added post-validation Windows replacement and junction-retarget integration
  coverage at the process-creation boundary.
- Retained registered batch scripts against replacement in addition to their
  immutable command launcher.
- Added spawned-process reroute races, committed-reservation crash recovery,
  execution-start crash recovery, and transactional rollback coverage.
- Persisted reroute reservation state in recovery and final-report evidence.

## 0.5.1

- Made recovery process discovery tri-state and fail closed on access denial and
  other indeterminate operating-system results.
- Bound command launch to mandatory immutable registration using retained
  deny-write/delete handles on Windows and post-launch image verification.
- Separated routing dispositions from actual provider execution attempts and
  reconciled reports against provider run evidence.
- Added atomic SQLite reroute consumption and destination-attempt reservation.

## 0.5.0

- Exercised controlled command executables through the complete author, independent
  review, repair, post-repair review, semantic verification, and evidence workflow.
- Added durable provider ownership checkpoints, incremental redacted logs, and
  retained-handle restart recovery that blocks ambiguous descendants.
- Added same-run selected-stage retries with stage-attempt identities, explicit
  authorization records, stable provider registration digests, truthful fresh
  instance identities, downstream invalidation, and irreversible-stage rejection.
- Added active waiver revocation and structured desktop evidence views for routing,
  provider identities, commands, verification, findings, logs, hashes, and Git results.
- Added rendered Windows Tk validation that navigates the real notebook, invokes the
  dashboard Refresh callback, verifies its status update, and records structured
  smoke evidence.

## 0.4.0

- Routed automatic and provider-specific desktop policies through discovered command
  and local-model adapters with independent review selection.
- Added startup interruption classification, immutable explicit retry attempts, and
  irreversible-stage retry rejection.
- Connected exact-scoped commit and push authority to durable lifecycle stages.
- Persisted live evidence roots, semantic command records, waiver details, Git
  results, retry history, and lifecycle notifications.
- Added a packaged rendered-Tk diagnostic mode with explicit unavailable reporting.

## 0.3.0

- Connected desktop tasks to the production orchestrator and durable lifecycle.
- Added approval/rejection, pause/resume, cancellation, live status polling,
  evidence actions, interactive setup, and lifecycle notifications.
- Added semantic command evidence, scoped waivers, and exact Git authorization.
- Added unified acceptance pilots and adversarial authorization coverage.

## 0.2.0

- Added versioned SQLite storage, migrations, backup/export, and legacy evidence import.
- Added full durable lifecycle, semantic verification binding, and tamper-evident reports.
- Added provider discovery, command adapters, deterministic independence routing, and
  loopback-only Ollama support.
- Added local desktop UI, first-run diagnostics, project/task/authorization workflows,
  notifications, history, and deterministic demonstration.
- Added dedicated Git safety, security controls, Windows packaging, documentation,
  and productization test coverage.
