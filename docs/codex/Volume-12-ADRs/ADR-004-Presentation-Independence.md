# ADR-004 — Presentation Independence

## Document Control

| Field | Value |
|---|---|
| Document ID | ADR-004 |
| Title | Presentation Independence |
| Version | 1.1.0 |
| Status | Approved |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Context

DS-001 §16 (Presentation Independence, a Foundational Principle) and §12's ninth Product Experience Principle both state that workspace layout shall not determine enabled analytical capability. DS-002's DS-PRD-003 and DS-007's DS-UX-001 (Presentation Independence Enforcement) instantiate this as a testable requirement: hiding, moving, removing, or rearranging a widget must never disable, gate, or otherwise depend on for its continued existence any underlying enabled capability, data source, or Sage evidence access. This ADR formalizes the principle architecturally so no future UI pattern can repurpose widget visibility into a capability gate without a new ADR.

## Decision

Workspace layout and widget visibility shall not determine enabled analytical capability or Sage evidence availability.

## Consequences

### Positive

- Users can freely customize, hide, or remove workspace widgets without fear of silently losing functionality, data access, or Sage evidence — directly supporting DS-001's "No Silent Capability Changes" principle.
- Prevents a class of dark pattern where hiding a widget is used as an implicit, non-obvious way to disable a capability; capability changes require their own explicit, distinguishable action (e.g., a Settings/Integrations surface).
- Gives Sage a stable evidence-availability contract: Sage's available evidence is governed by enabled capabilities, permissions, integrations, configuration, and data — never by which widgets happen to be visible in the current workspace.

### Negative

- Requires the UI architecture to maintain a strict separation between capability state and presentation state (DS-UX-001) as an ongoing implementation discipline, not a one-time fix — every widget-visibility change must be verified to have zero effect on enabled capability or calculation results.
- Adds a regression-testing obligation (DS-UX-001's acceptance criteria) that must be re-run whenever workspace or widget behavior changes, to confirm no client code path uses widget visibility as an input to a capability-gating decision.

## Alternatives Considered

No alternative model (e.g., allowing widget visibility to double as a lightweight capability toggle) is recorded in this decision's approved history. DS-001 §16 and DS-UX-001 state the separation as an unconditional requirement, leaving no partial-coupling variant for this repair to record as a considered-and-rejected alternative.

## Related Requirements

- DS-001 — Executive Vision & Product Foundation, §12 (Product Experience Principles — Presentation Independence, No Silent Capability Changes), §16 (Presentation Independence)
- DS-002 — Software Requirements Specification: DS-PRD-003
- DS-007 — UI/UX Bible: DS-UX-001 (Presentation Independence Enforcement), DS-UX-002 (Workspace Studio Baseline Layout)

## Decision History

| Version | Date | Status | Owner | Summary |
|---|---|---|---|---|
| 1.0.0 | 2026-07-23 | Approved | TheSinnerMan | Approved initial controlled baseline; metadata normalization of the existing decision. Decision content unchanged. |
| 1.1.0 | 2026-07-24 | Approved | TheSinnerMan | Consolidated cleanup pass: populated previously template-minimal Context, Consequences, Alternatives Considered, and Related Requirements sections from already-approved DS-001/DS-002/DS-007 content. Decision content unchanged; approved status and authority preserved. |
