# Codex subscription provider and Keeper Provider Host

Keeper 1.0 supports the official standalone Windows Codex CLI as an
authoring-only provider through KeeperAuthority 1.7.1, Authority protocol 7,
schema 6, and the per-user `keeper-provider-host/1` protocol. The Provider Host
is an unelevated execution deputy. It cannot register, qualify, reserve, approve,
spend, change policy, or fabricate Authority state.

The supported contract uses the Founder's existing ChatGPT subscription
authentication. OpenAI API keys, API billing, paid fallback, credit purchase,
automatic account switching, automatic provider switching, Low effort, and
self-review are prohibited.

## Production boundary

The production path is:

1. KeeperAuthority authenticates the local Executive client and owns provider
   registration, qualification, usage, session, workspace, and launch policy.
2. KeeperAuthority and the logged-on Provider Host mutually authenticate over a
   local-only named pipe using separate asymmetric identities and exact Windows
   peer identity checks.
3. KeeperAuthority signs one expiring, sequenced request bound to the complete
   project, charter revision, workflow, WorkItem, assignment, attempt,
   registration, qualification, executable, provider, model, effort, command,
   workspace, environment, network, usage, and cancellation declaration.
4. The host transactionally claims the sequence, nonce, launch, and canonical
   workspace before external execution. Replays and overlapping workspaces fail.
5. The host builds an allowlisted environment from its already-running user
   process. It never asks the service to reconstruct or export a user profile.
6. The host locks and remeasures the executable, derives a restricted
   Medium-integrity token, creates the process suspended, persists `STARTED`,
   assigns the complete tree to a kill-on-close Job Object, and only then resumes.
7. The host signs a bounded completion receipt. KeeperAuthority verifies the
   exact envelope and provider-input digests before accepting completion.

`execute_provider(attempt_id)` remains ID-only. Provider input is immutable,
server-owned Authority state and cannot be replaced at execution time.

## Identity, transport, and replay

The pipe rejects remote clients and has an explicit DACL that denies the
Restricted Code SID carried by every supported provider token before allowing
SYSTEM and the exact interactive user. The Host uses a dedicated measured
`KeeperProviderHost.exe`; a shared Python interpreter or zipapp cannot satisfy
the Authority peer-executable binding. The Host's non-exportable per-user CNG
key and versioned installation tree use the same Restricted Code exclusion, so
a compromised supported provider cannot sign as, replace, or connect as the
Host merely because it retains the Founder's user-profile SID.
Both peers validate SID, session, executable path, SHA-256, process identity,
and key identity. Every signed message carries a nonce, monotonic sequence,
issue time, expiry, maximum TTL, and exact body digest. Future-issued, expired,
replayed, reordered, mismatched, test-composition, or identity-invalid messages
fail closed.

Host lifecycle state is durable and visible as `STARTING`, `READY`, `PREPARING`,
`CLAIMED`, `STARTED`, `RUNNING`, terminal, or `UNCERTAIN`, plus `LOCKED`,
`DRAINING`, `STOPPED`, and `STALE`. New work rejects outside the ready path.
Lock cancels active work; logoff cancels and stops. Restart converts unresolved
external-effect states to `UNCERTAIN`; non-idempotent work is never retried
automatically.

## Credentials and environment

Credentials never cross the service/host protocol. The host uses only the
official CLI's existing per-user ChatGPT session and exposes only a one-way
account identity digest plus public plan/model/usage observations.

The environment allowlist excludes API keys, access tokens, cookies, proxy
settings and credentials, paid-fallback controls, and mutable provider/model
overrides. Values are not logged. The Authority records only safe names,
classifications, and digests. Provider output remains untrusted structured data;
provider-generated code is never imported, evaluated, or executed inside the
trusted Executive process.

## Codex provider declaration

Registration pins the canonical executable path, SHA-256, size, file identity,
valid OpenAI Authenticode publisher/certificate, CLI version, one model,
Medium/High efforts, exact Windows SID/session/profile, ChatGPT subscription
account digest, capability observation, pricing authority, and conservative
usage policy. Qualification and every launch revalidate those values.

The Authority-owned invocation uses no command shell and fixes model, effort,
workspace, prompt, schema, output paths, timeout, and sandbox policy. Mutable
user configuration cannot widen it. A single Codex identity is authoring-only;
independent review waits for a separately qualified reviewer.

## Usage semantics

`INCLUDED_SUBSCRIPTION` is not `FREE`: it means zero authorized incremental API
charge under the existing subscription and bounded observed capacity. Unknown
capacity uses a conservative durable launch budget. Exhaustion becomes
`WAITING_FOR_USAGE_RESET`; no automatic retry, purchase, fallback, provider
switch, or account switch occurs. A durable wait clears only with a fresh
validated provider observation allowed by the existing reset policy.

## Per-user lifecycle

Provider Host artifacts are versioned beneath the canonical per-user
`%LOCALAPPDATA%\Programs\DarkSage\KeeperProviderHost` root. The lifecycle
accepts the dedicated `KeeperProviderHost.exe` only as part
of its complete standalone distribution. A SHA-256-bound package manifest names
every runtime file, size, and digest; missing, additional, changed, linked, or
escaping files fail closed. Installation copies and revalidates the entire
distribution, while the executable retains its separate Authority identity.
Current selection is atomic and retains one verified rollback generation.
Install, same-version repair, drain-before-update, rollback, crash recovery, and
data-preserving uninstall are supported by `keeper provider-host`. The at-logon
launcher stores no password and quotes every trusted path. Both its file and
containing Startup namespace deny the restricted provider token, preventing
delete-and-replace attacks through parent-directory rights.

An installed Host with no signed enrollment receipt exits successfully in
`INSTALLED_UNENROLLED` bootstrap-only state. It does not open the runtime pipe,
accept requests, register or qualify providers, reserve usage, or execute a
model. A Founder-authenticated protocol-7 enrollment uses an exact Host-signed
proposal, one short-lived Authority-signed grant, one Host proof, and one
Authority-signed receipt. The proposal binds the service key, protocol/schema,
user SID/session/profile, canonical install and Startup selection, manifest,
executable path/hash/file identity, exact Authenticode status and signer identity
when present, non-exportable Host public key, pipe, nonce, expiry, and generation.
KeeperAuthority independently remeasures those values under the authenticated
named-pipe client before it persists a one-winner `PENDING` record.

Completion stores `ACTIVE` before the gateway is exposed. Lost responses use
exact, idempotent reconciliation; conflicts, expiry, replay, downgrade, and
ambiguous activation fail closed. Revocation first persists a durable
`UNCERTAIN` execution fence, disables the live gateway, and then persists
`REVOKED`; a lost response can retrieve the same signed denial after a fresh,
exact Founder authentication. A revocation-fenced `UNCERTAIN` record cannot be
reactivated by enrollment reconciliation after restart. Host enrollment never
creates a provider binding. Registration and qualification remain later
Authority-owned operations, and the Host reports `NO_QUALIFIED_PROVIDERS` until
exact qualification is durably bound.

Qualification begins against an enrolled, ready Host with no provider binding.
KeeperAuthority durably stages the qualified observation as `UNCERTAIN` before
requesting the exact Host binding, then publishes the registration and
qualification as `QUALIFIED` atomically only after the Host acknowledges the
same binding. If the Host commits the binding but its response is lost,
`reconcile_provider_qualification(registration_id)` re-sends only the stored
Authority-owned binding and atomically completes the same records. It accepts no
replacement provider input and remains one-winner and idempotent.

The supported shipped recovery command is:

```powershell
keeper-authority codex-reconcile-qualification `
  --registration-id <persisted-registration-id> `
  --output-directory <new-empty-response-directory> `
  --apply
```

The command exclusively claims its response directory, performs exactly one
reconciliation request, and persists the complete public Authority response
before extracting identifiers. Authority diagnostics report
`QUALIFICATION_UNCERTAIN` and `RECONCILE_PROVIDER_QUALIFICATION` until the exact
durable pair is reconciled. Re-running against an already claimed response
directory or an already reconciled registration fails closed.

The installed Host executable owns the supported production enrollment surface;
no protected configuration file is edited by hand. After the matching protocol-7
Authority update is healthy, the Founder runs:

```powershell
KeeperProviderHost.exe enrollment-status
KeeperProviderHost.exe enroll --generation 1
```

`enroll` displays the normal Windows Founder credential dialog and then performs
the proposal/grant/proof/receipt exchange through the authenticated Authority
pipe. Interrupted flows resume only through `resume-enrollment` or
`reconcile-enrollment`. Revocation requires the exact enrollment ID, receipt
digest, and next generation through `revoke-enrollment`; arbitrary receipt or
configuration input is not accepted.

All source verification uses disposable `C:\tmp` roots. Real installation,
Startup creation, Authority update/restart, Founder enrollment, Codex
registration/qualification, and any model execution remain distinct live
operations requiring their applicable Founder authorization. Disposable CLI
roots and no-op drain callbacks are test composition only; the Phase 2 runbook
uses the canonical roots and supported Authority lifecycle.

## Desktop truth

The Providers and Safety views project only read-only, redacted service state:
host installed/online state, lifecycle state, protocol compatibility, provider
registered/qualified state, execution/usage state, and any explicit Founder
action. Raw executable paths, account identities, credentials, and host keys are
not displayed. UI state grants no Authority effect.
