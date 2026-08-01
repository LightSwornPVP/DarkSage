# Keeper User Guide

Keeper opens as an executive control center with project-scoped durable state.
The project selector in the header changes the active project and persists that
selection across restart. Home never combines one project's charter or work with
another project's status.

## From conversation to approved work

1. Describe the outcome, boundaries, providers, workspace, budget, and exclusions
   in Conversation.
2. Keeper creates a proposed charter. Conversation text is not approval.
3. Review Founder approval from Home. The review shows the exact deliverables,
   constraints, non-goals, delegation mode, budget, providers, tools, workspaces,
   evidence, review requirements, and unresolved questions.
4. Choose **Approve with Windows** only when the exact charter is correct.
   Keeper then uses native Windows Founder authentication. The Tk dialog grants no
   authority by itself.
5. After authenticated activation, Keeper commits one charter-derived workflow
   plan and all work items atomically.

If authentication is canceled, rejected, unavailable, or expires, no workflow is
created. A durable approval or activation interrupted before UI refresh is
reconciled from authoritative state on the next exact attempt.

## After the one Founder approval

For an approved full-delegation charter, Keeper activates a project- and
charter-scoped delegated grant and continues in the background. It selects only
qualified, charter-approved, non-paid providers; claims usage, sessions, and one
canonical producer workspace; executes dependency-ready stages; sends exact typed
evidence to a separate read-only reviewer workspace; applies accepted review or one
bounded repair path; and closes the workflow only after validated evidence.

Routine sequencing, provider choice, testing, review, and bounded repair do not ask
for another approval. Usage exhaustion, `UNCERTAIN` effects, expired/revoked grants,
changed charters, prohibited actions, or unavailable independent capacity stop and
surface an explicit durable state instead of guessing or retrying.

## Product areas

- **Home**: current project, approval state, workflow, usage, recent evidence,
  KeeperAuthority health, and presentation-only Sage status.
- **Conversation**: durable Founder and Keeper project-intake history.
- **Projects**: complete charter scope and authority boundaries.
- **Workflow**: charter-derived stages, roles, providers, status, and usage waits.
- **Providers**: provider/session health and shared usage pools.
- **Evidence**: validated evidence, typed references, and independent reviews.
- **Safety**: KeeperAuthority, delegated-mode, uncertainty, pause, and prohibited
  action status.
- **Settings**: ordinary local settings and diagnostics. Security, service,
  payment, deployment, and live-trading toggles are unavailable.

Provider launch, retry, pause/resume, cancellation, recovery, and exceptional
actions remain authoritative service operations. UI labels and buttons never

## Daily launch

Build the standalone artifact with `scripts/build-keeper.ps1`, then launch it with:

```powershell
python C:\path\to\keeper.pyz
```
bypass the Executive, Pass B, or KeeperAuthority boundaries.
