# DS-018 — Sage Deployment and Intelligence Architecture

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-018 |
| Title | Sage Deployment and Intelligence Architecture |
| Version | 0.1.0 |
| Status | Draft (Foundation Skeleton) |
| Project | DarkSage |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated. Structural skeleton only. Does not alter DS-001–DS-014, and in particular does not alter or reinterpret DS-003 (Sage AI Bible)'s existing DS-SGE-NNN behavioral requirements or ADR-002 (Sage Cannot Bypass the Risk Engine)/ADR-006 (Bounded Sage Agency).

Parent: [DS-003 — Sage AI Bible](../Volume-03-Sage/DS-003-Sage-AI-Bible.md).

## 1. Purpose

Define the **deployment and infrastructure architecture** for Sage across two distinct operating contexts — the Founder's private, local Sage instance and the Customer Edition's cloud-hosted Sage service — while DS-003 continues to own Sage's *behavioral* requirements (what Sage may and may not do). This volume answers "where does Sage run and how is it routed/versioned," not "what may Sage decide."

## 2. Scope

- Founder Local Sage: deployment model, privacy guarantees, and why it remains permanently private (never shipped to a customer build).
- Customer Cloud Sage: cloud-hosted deployment, request routing, and why it is cloud-first rather than a downgraded local model.
- Hybrid design: how the two share a behavioral contract (DS-003/ADR-002/ADR-006) while differing in deployment.
- Model/prompt routing and versioning (which model version serves which request, and how that is tracked for reproducibility/audit).
- Research-tool integration surface (Sage-assisted research features, e.g. DS-RSH's Sage-orchestrated workflow, DS-RSH-006).
- "Why not this trade?" explanation feature's architectural home.
- Sage usage quotas (architecture only; entitlement *values* are DS-019's scope).
- Sage privacy and failure-mode behavior (what happens to a request when Sage is unavailable — must degrade honestly, never fabricate a response).
- **Founder Sage Developer Mode** (`FEAT-0268`, added 2026-07-26): the Founder-only, private, local-workstation coding/research assistant this volume owns primary responsibility for. See Section 14.

## 3. Non-Goals

- Does not define or alter Sage's behavioral boundaries — DS-003, ADR-002, and ADR-006 remain sole authority there.
- Does not define entitlement quota *values* or billing — DS-019.
- Does not permit Sage to bypass deterministic validation under any deployment model; this is restated, not reinterpreted, from ADR-002.

## 4. Owner Requirement Families

- **DS-SYG** (new, proposed) — Sage Deployment. Primary volume: DS-018. Deliberately distinct from the existing **DS-SGE** family (DS-003), which owns Sage's *behavioral* requirements and is unchanged by this volume.

## 5. Supporting Requirement Families

- DS-SGE (DS-003) — the behavioral contract this volume's deployment architecture must serve without altering.
- DS-RSH (DS-002/Volume-02-Product/requirements/DS-RSH-Research-Intelligence.md) — Sage-orchestrated research workflow (DS-RSH-006) this volume must host.
- DS-JRN (DS-002/Volume-02-Product/requirements/DS-JRN-Journal-and-Review.md) — Sage coaching boundary (DS-JRN-005) this volume must host.
- DS-SCA (DS-008) — DS-SCA-028 (research/journal data protection) governs data this volume's Sage deployments touch.

## 6. Dependencies

- DS-003 (Sage AI Bible) — behavioral contract (immutable from this volume's perspective).
- ADR-002 (Sage Cannot Bypass the Risk Engine), ADR-006 (Bounded Sage Agency) — architectural invariants this volume's deployment design must preserve regardless of local/cloud routing.
- DS-015 (Editions) — Founder Local Sage's permanent exclusion from the Customer Edition build.
- DS-017 (Local-First and Cloud Migration Architecture) — general local/cloud provider-abstraction pattern this volume specializes for Sage.
- DS-019 (Commercialization) — Sage usage quota *values* and entitlement tiers.
- DS-015 (Editions) — Founder Sage Developer Mode's exclusion from every customer build (same mechanism as Founder Local Sage).
- DS-021 (Security, Device Trust, and Privacy) — sandboxing, secrets, repository security, and Founder-asset exclusion for Founder Sage Developer Mode.
- DS-023 (Reliability, Operations, and Data Governance) — logging, diagnostics, rollback, recovery, and resource limits for Founder Sage Developer Mode.

## 7. Major Sections (Planned for Full Draft)

1. Founder Local Sage Deployment Model
2. Customer Cloud Sage Deployment Model
3. Hybrid Behavioral-Contract Consistency
4. Model/Prompt Routing and Versioning
5. Research-Tool Integration Surface
6. "Why Not This Trade?" Explanation Architecture
7. Sage Quota Architecture (values deferred to DS-019)
8. Sage Privacy and Failure-Mode Behavior

## 8. Cross-Volume References

- DS-003 (Sage AI Bible), DS-004 (Technical Architecture), DS-008 (Security Architecture), DS-015 (Editions), DS-017 (Local-First and Cloud Migration Architecture), DS-019 (Commercialization, Subscriptions, and Entitlements).

## 9. Acceptance Criteria (Placeholders)

- [ ] Founder Local Sage never appears in any Customer Edition build artifact (verified mechanically, cross-referenced with DS-015).
- [ ] Every Sage deployment mode (local, cloud) enforces the identical ADR-002/ADR-006 behavioral boundary; no deployment-specific bypass exists.
- [ ] A Sage-unavailable condition degrades honestly (explicit "Sage unavailable" state) and never fabricates a response.

## 10. Traceability (Placeholders)

- [ ] DS-SYG-001 … (allocated in `docs/features/FEATURE_GOVERNANCE.md`; full requirement text deferred).

## 11. Release-Stage Responsibilities

| Stage | Responsibility |
|---|---|
| Stage 3 (Founder Workstation Beta) | Founder Local Sage is the only Sage deployment; remains fully private. |
| Stage 4 (Customer Cloud Beta) | Customer Cloud Sage deployment enters beta, cloud-first by design (no customer-facing local-Sage variant). |
| Stage 5 (Initial Commercial Release) | Cloud Sage is a general-availability, quota-governed capability of the Customer Edition. |

## 12. Open Decisions

- Whether Customer Cloud Sage ever offers a customer-hosted (self-managed) deployment option, or remains DarkSage-hosted only.
- Model-routing versioning granularity (per-request vs. per-session) — deferred to full draft.

## 13. Known Risks

- Any architectural change that makes local/cloud Sage diverge in *behavior* (not just deployment) would violate ADR-002/ADR-006 and must be treated as a Critical-severity defect once fully drafted.
- Cloud Sage cost exposure is a commercialization risk shared with DS-019 and DS-023 (cost controls).

## 14. Founder Sage Developer Mode (`FEAT-0268`) — Skeleton, Added 2026-07-26

**Status:** structural skeleton only, matching the rest of this volume; not a full requirement draft. DS-018 is the **primary owner**; see DS-015 (edition/repository boundary), DS-021 (sandboxing/secrets/repository security), DS-023 (logging/diagnostics/rollback/recovery/resource limits) for the co-owned safety surface.

Capability surface (groundwork begins Stage 1; usable private version targeted for Stage 3 Founder Workstation Beta):

- Coding-model routing: a clear, explicit distinction between reasoning models and coding-focused models, with the Founder able to select or let Developer Mode select the appropriate model per task.
- Repository inspection and code explanation of the DarkSage codebase.
- Code generation and modification, and test generation.
- Build, runtime, and test-failure debugging/diagnosis.
- Migration and documentation generation.
- Experimental indicator and strategy development (research/prototyping, distinct from and never feeding directly into live deterministic execution — see DS-004/ADR-002).
- Execution of approved local development tools only (see DS-021 for the sandboxing/allowlist boundary).
- Diff preparation and commit preparation for **explicit Founder review** — Developer Mode never advances a change from one state (suggested → working tree → staged → committed → pushed → deployed) to the next without that specific Founder action; see DS-023 for state-tracking requirements.
- Maintained task history and development context across a work session.
- **No automatic production deployment** — Developer Mode cannot deploy any code, artifact, or configuration automatically to a production environment.
- **No broker or trade-execution authority of any kind** — the existence of coding tools grants no order-submission, no bypass of the Risk Engine, and no authority over any deterministic trading control (ADR-002 applies unchanged).
