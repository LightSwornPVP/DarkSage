# Keeper 1.0 Personal-Use Threat Model

Version: 1.0
Decision date: 2026-07-28
Owner: Founder
Status: Authoritative for Keeper Completion Pass A

## Authority and audit use

This document is the controlled threat boundary for Keeper 1.0 Completion Pass A.
Security findings are release blockers only when they are reachable through a
supported Keeper operation or violate an in-scope boundary below. The general
repository security and trading rules remain higher-authority governance; this
document defines which adversaries and post-compromise conditions Pass A claims
to resist.

Keeper 1.0 is a personal-use, single-Founder system. It is not a public
multi-tenant service, an arbitrary plugin marketplace, or a sandbox that treats
its own installed Executive interpreter as hostile.

The personal-use scope never excuses a failure reachable through ordinary Founder
use, supported provider execution, normal restart, documented configuration,
supported concurrency, crash recovery, public application methods, or supported
persistence workflows.

## Trust boundary

Trusted components are:

- installed Keeper Executive and UI application code;
- KeeperAuthority;
- repository-configured production adapters;
- production persistence code;
- Founder-approved provider registrations;
- deterministic authority, risk, and policy evaluation;
- the Founder-authentication boundary; and
- Windows and local operating-system security during normal operation.

Untrusted inputs and components are:

- every model response and task-result claim;
- generated code before review and verification;
- provider process stdout, stderr, files, and evidence;
- external documents, webpages, research, and downloaded artifacts;
- proposed commands and tool requests;
- model-generated review claims; and
- any future plugin running outside the trusted process.

Provider output is data. It is never Founder authority, completion authority by
itself, or permission to commit, push, deploy, publish, spend, access credentials,
trade, or perform another protected action.

## In-scope threats

Keeper 1.0 defends against:

- incorrect, misleading, or malicious model output;
- prompt injection and hostile instructions in external content;
- model scope expansion, Founder impersonation, and self-approval;
- fabricated tests, completion evidence, qualification, or completion;
- provider-process compromise and attempts to read protected Authority state;
- unqualified or unauthorized provider selection and execution;
- unsupported provider capability or role claims;
- wrong provider, executable, session, workspace, charter, task, or project binding;
- duplicate material execution and unsafe retry after uncertain execution;
- cancellation, revocation, completion, and restart races;
- replayed or stale approvals, capabilities, attempts, and evidence;
- spending or paid-provider fallback without explicit authority;
- unauthorized commit, push, deployment, publication, purchase, credential access,
  live trading, or destructive action;
- application crashes, process interruption, incomplete persistence, and database
  corruption;
- supported concurrent Executive activity;
- supported restart, reconciliation, backup, and restore workflows;
- accidental local configuration mistakes; and
- supported production/test composition mistakes.

## Out-of-scope post-compromise threats

The following do not block Keeper 1.0 personal-use release:

- arbitrary code already executing inside the trusted Keeper Executive Python
  interpreter;
- deliberate same-process monkey-patching of trusted classes or module functions;
- `object.__setattr__`, reflection, debugger manipulation, direct private-field
  mutation, closure inspection, or private-constructor misuse;
- deliberate replacement of trusted application internals by the Founder or a
  malicious local administrator;
- manual same-user modification, replacement, or rollback of the private Executive
  database and its integrity records outside the restore workflow;
- malicious kernel, driver, hypervisor, or operating-system compromise;
- physical compromise of the Founder computer;
- theft of Founder Windows credentials;
- arbitrary code execution under the Founder account outside approved Keeper
  provider isolation; and
- unsupported third-party plugins loaded into the trusted process.

These conditions are post-compromise or administrator-level scenarios. Existing
maintainable object identity and sealing checks remain defense-in-depth, but Pass A
does not add increasingly elaborate Python sealing to resist them.

## Provider security model

Approved providers may include OpenAI (including Codex), Anthropic, Google Gemini,
xAI Grok, GitHub Copilot, approved local models, and later explicitly approved
reputable providers. Approval never makes provider output trusted.

The supported provider boundary requires:

- explicit registration and qualification;
- capability, role, and restriction eligibility;
- exact executable and session identity;
- service-owned attempt reservation and launch;
- authenticated completion and structured evidence;
- distinct qualified reviewer execution when required;
- project, charter, task, workspace, cost, and usage binding;
- cancellation, revocation, and exactly-once semantics; and
- no provider access to KeeperAuthority protected state.

## No provider-generated code in the trusted process

Provider-generated code is never loaded, imported, evaluated, compiled, or
executed inside the trusted Keeper Executive interpreter. The Executive package
has no runtime plugin loader or provider-output import API. A static regression
rejects dynamic loading primitives in that package.

Generated code may execute only through KeeperAuthority-managed restricted
provider processes, isolated test/build processes, approved project workspaces,
explicit deterministic tools, or separately reviewed and installed application
updates.

For Keeper 1.0, provider adapters are installed trusted application components.
Arbitrary third-party plugins do not run in-process. Future plugins default to
out-of-process execution, declare a capability and authority envelope, treat
their output as untrusted, and require Founder approval for installation or
privilege expansion.

## Persistence and recovery boundary

SQLite is the sole authoritative Executive commit boundary during normal
operation. WAL mode, full synchronous durability, foreign keys, explicit
transactions, schema constraints, compare-and-swap updates, durable attempt IDs,
unique bindings, one-use approvals, budget reservations, and restart
reconciliation protect supported operation.

There is no database-commit-then-lineage-file-append protocol. Backups are atomic
SQLite snapshots outside the business transaction path. Restore is an explicit
trusted maintenance workflow: authenticate the Founder, stage and integrity-check
the backup, pause every nonterminal project, reconcile against KeeperAuthority,
record a new in-database recovery epoch, and only then replace the live database.

KeeperAuthority remains authoritative for provider attempts, launches,
cancellation, and completion. Restored Executive planning state cannot override
newer authenticated Authority truth. Uncertain execution remains non-retry-safe.
Normal startup fails closed on genuine SQLite or foreign-key corruption.

## Supported concurrency

Completion Pass A supports Option B: multiple Executive runtime writers using the
same SQLite database. This is retained because the existing application and
restart tests deliberately exercise two runtime instances. Supported writes use
SQLite transactions, `BEGIN IMMEDIATE`, unique constraints, and exact CAS; they no
longer depend on a second file commit.

An explicit restore is a maintenance operation, not a concurrent writer
operation. Other Executive writers must be stopped before it begins. Provider
processes remain independently concurrent behind KeeperAuthority.

## Finding classification

A finding remains in scope when a normal public API, supported configuration,
provider process, crash, restart, persistence workflow, or supported concurrency
path can reach it.

Class replacement, closure mutation, evaluator or selector private replacement,
module monkey-patching, reflection, and manual database replacement are future
hardening items when their prerequisite is arbitrary same-process or same-user
post-compromise access.

## Future stronger boundary

A public, multi-user, or unknown-plugin product requires a new threat-model
version and a separate service boundary:

```text
Desktop/UI
→ isolated Keeper Executive Service
→ KeeperAuthority
→ restricted provider processes
```
