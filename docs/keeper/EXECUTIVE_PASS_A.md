# Keeper Executive Completion Pass A

## Product boundary

Keeper Executive is the conversation-first project manager above the independently
protected Authority Service. It converts Founder conversation into a versioned
Project Charter, generates a workload-specific workflow, selects qualified
specialists, validates authority deterministically, reviews evidence, requests
repair, and resumes from durable state.

The executive never signs provider records, qualifies providers, fabricates
completion, reads protected keys, or broadens Authority IPC. Production provider
execution is injected through the narrow lifecycle operations already exposed by
the Authority Service.

## State machines

Projects move through intake, clarification, charter drafting and approval,
activation, planning, execution, review, waiting or blocked states, pause, and a
terminal completed, canceled, or failed state. Tasks move through proposed,
ready, assigned, running, review, repair, completion, blocked, failed, canceled,
or skipped states. Explicit transition maps reject arbitrary completion.

Approved charter content is immutable. Activation is a project-to-charter
binding rather than a mutation of the approved record. Material changes create a
new draft revision with exact differences, reason, authority basis, and a link to
the prior version. Old approvals match neither the new charter identity nor its
revision.

## Conversation and charter model

Intake values retain one of four origins: explicit Founder statement, high
confidence inference, proposed assumption, or unresolved question. A future
desktop client can revise structured values without losing the source
interaction. Charter records include purpose, outcome, deliverables, non-goals,
criteria, constraints, assumptions, questions, timeline, budget, tools,
providers, workspaces, privacy, risk, delegation, authority, escalation, review,
evidence, completion, version, and Founder approval fields.

## Delegation and deterministic authority

Advisory mode permits analysis, planning, drafting, and reading. Delegated mode
permits routine actions explicitly listed by the charter. Full Delegation permits
bounded material work inside the same envelope. It is not unlimited authority.

Every proposed action is evaluated against the active revision, project state,
action class, target, provider, tool, scope, cost, reversibility, risk, data
classification, external side effects, expiry, revocation, workspace roots, and
bound approvals. Ambiguity fails closed. Protected deletion, history rewrite,
credential access, security-boundary change, live trading, financial-authority
change, governance change, and irreversible destruction are non-delegable.
Push, production deployment, external publication, purchases, spending, and
commit authorization remain separately approvable.

## Dynamic workflow and specialists

The planner has workload-aware strategies for software, research, video, music,
writing, and general projects. Each generated stage explains its purpose and
rationale and creates durable tasks with dependencies, inputs, outputs,
capabilities, authority class, evidence, review, and retry policy.

Selection considers project type, capability, qualification, charter provider
restrictions, availability, credentials, effort, cost, prior results, and
independence identity. Specialists receive a shared project brief and a
least-context task guide. They cannot change their role, expand scope, alter the
charter, self-grant authority, or claim completion without outputs and evidence.
Independent review requires a distinct independence identity. Repair records the
failed criterion, evidence, correction, successful work to preserve, retry
limit, and repair assignment.

## Persistence, restart, and surfaces

Schema version 2 adds hash-checked project, charter, workflow, task, approval,
memory, decision, assumption, conversation, and assignment stores plus
foreign-key relationship records. Migrations are idempotent and preserve the
existing schema and protected Authority state.

The runtime performs one durable step per call. Completed tasks are never
relaunched after restart. Missing authority, provider, credential, independence,
input, or workspace scope enters an explicit pause or waiting state. Revocation
halts new launches and prevents resume until new Founder approval exists.

The application view model exposes Keeper conversation, project summary, charter
history, delegation and limits, unresolved questions, workflow and stage status,
tasks, assignments, decisions, assumptions, approvals, blockers, evidence, and
pause/resume/cancel controls. The desktop dashboard can consume this model while
keeping conversation as the primary interaction.

## Pass B extension points

- `SpecialistProfile.session_id` and the selector allow multiple sessions per
  provider without changing task records.
- Waiting states reserve provider reset, credential, external system, and usage
  reset transitions.
- Cost and provider fields allow shared usage-pool accounting.
- Workspace fields and readiness checks allow future write reservations and
  cross-worktree locking.
- `ProjectStatusView` is presentation-independent for the final black, gold,
  gray, and white desktop experience.

Pass A does not automatically purchase usage, wait for provider resets, publish,
deploy, enable live trading, or implement the final production desktop shell.
