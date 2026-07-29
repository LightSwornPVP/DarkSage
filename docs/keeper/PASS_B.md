# Keeper Completion Pass B

Pass B turns the approved Executive and Authority foundation into a
conversation-first personal project system. It adds durable provider sessions,
shared usage accounting, assignments, attempts, evidence, reviews, workspace
leases, write claims, recovery checkpoints, delegated-mode records, control-room
views, and the Sage presentation boundary.

## Product flow

1. The Founder describes a project in conversation.
2. Keeper extracts durable intake facts and proposes a versioned Project
   Charter.
3. Conversation text remains non-authoritative. The existing Founder
   authentication and charter activation boundary supplies authority.
4. Keeper selects an adaptive workflow from the active charter's project type,
   deliverables, evidence requirements, and review requirements.
5. Assignments bind immutable provider, account, session, role, model,
   workspace, charter revision, authority-envelope digest, expected evidence,
   and usage policy.
6. Keeper reserves usage and workspace scope before launch, persists the
   attempt before calling an adapter, validates returned evidence as untrusted
   data, and requires independent review where the charter requires it.
7. The control room presents durable state, blockers, uncertainty, recovery
   prompts, and Authority health.

The workflow designer has separate adaptive strategies for software, research,
video, music, writing, design, marketing, business operations, and general
projects. It does not impose one universal coding pipeline.

## Durable storage

Pass B records are stored in the existing Keeper SQLite database. Migration
version 1 is recorded in `pass_b_schema_migrations`. Generic records use
revision-and-payload-hash compare-and-swap updates. Normalized claim tables
provide transactionally enforced uniqueness for workspace writers, protected
write scopes, usage reservations, and launch identity.

The inherited store configuration retains WAL mode, full synchronous behavior,
foreign keys, busy handling, integrity-checked backup behavior, recovery epoch,
and the Pass A restore fence. Adding Pass B tables does not introduce a
database-plus-file transaction protocol.

## Authority boundary

Pass B reuses `ProjectRecord`, `ProjectCharter`, workflows, Founder approvals,
and the production Executive facade. It does not create a second authority
system.

Provider adapters translate data only. They cannot approve, expand charters,
authorize side effects, or load provider-generated code into the Executive.
Launch calls carry an existing authority attempt identity; production
composition supplies the live Authority client.

## Supported entry points

- `scripts/keeper-pass-b-desktop.py` starts the conversation-first desktop
  shell with the production Executive and Authority client.
- `scripts/keeper-pass-b-pilot.py` runs the isolated deterministic DarkSage
  pilot and writes durable evidence.

The local/mock adapter is intended for diagnostics, tests, and isolated pilots.
Real remote transports are injected behind the stable adapter contract.
