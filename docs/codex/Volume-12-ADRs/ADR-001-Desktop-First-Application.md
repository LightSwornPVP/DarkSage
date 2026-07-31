# ADR-001 — Desktop-First Application

## Document Control

| Field | Value |
|---|---|
| Document ID | ADR-001 |
| Title | Desktop-First Application |
| Version | 1.1.0 |
| Status | Approved |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Context

DarkSage's initial product direction required choosing a primary client surface to concentrate engineering effort on for Phase 1 rather than building multiple client platforms in parallel. Per DS-001 §12 (Product Experience Principles) and DS-001's Current Product Direction statement, the desktop experience was adopted as the primary current product direction, with `ROADMAP.md` Phase 1 exit criteria (including a launching desktop app) built around it. This decision does not foreclose future companion clients — DS-004's DS-ARC-003 already records a Planned (Phase 9) mobile client under the same backend-authoritative architecture.

## Decision

DarkSage will be desktop-first while preserving future service/API extensibility.

## Consequences

### Positive

- Concentrates Phase 1 engineering effort on one authoritative client surface, matching `ROADMAP.md` Phase 1 exit criteria.
- Preserves future extensibility for additional client surfaces (mobile, web, API-driven companions) without committing them to current scope — DS-004's DS-ARC-003 (Mobile Client) already reserves this path as Planned/Phase 9.
- Reinforces the client/backend boundary (DS-ARC-001): the backend remains the sole authoritative source of trading and account state regardless of how many client surfaces eventually exist, so desktop-first does not create platform-specific trading logic that later clients would need to duplicate or reconcile.

### Negative

- Mobile and web users have no supported client until a later, separately-approved phase; DarkSage does not currently serve those platforms.
- Any user-authority, execution-boundary, or security work validated against the desktop client must be re-verified (not assumed) when a future client surface is added, since desktop-first is a scope decision, not a proof that the boundary generalizes automatically.

## Alternatives Considered

No alternative platform strategy (e.g., mobile-first, web-first, or simultaneous multi-platform launch) is recorded in this decision's approved history. Desktop-first was adopted directly as DS-001's stated current product direction; this repair records that context rather than introducing new alternatives that were never evaluated by the approved decision.

## Related Requirements

- DS-001 — Executive Vision & Product Foundation, §12 (Product Experience Principles), §17 (Current Product Direction)
- DS-004 — Technical Architecture: DS-ARC-001 (Client/Backend Architectural Boundary), DS-ARC-002 (Desktop Client), DS-ARC-003 (Mobile Client, Planned/Phase 9)

## Decision History

| Version | Date | Status | Owner | Summary |
|---|---|---|---|---|
| 1.0.0 | 2026-07-23 | Approved | TheSinnerMan | Approved initial controlled baseline; metadata normalization of the existing decision. Decision content unchanged. |
| 1.1.0 | 2026-07-24 | Approved | TheSinnerMan | Consolidated cleanup pass: populated previously template-minimal Context, Consequences, Alternatives Considered, and Related Requirements sections from already-approved DS-001/DS-004 content. Decision content unchanged; approved status and authority preserved. |
