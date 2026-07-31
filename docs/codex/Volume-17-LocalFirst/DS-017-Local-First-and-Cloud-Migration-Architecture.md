# DS-017 — Local-First and Cloud Migration Architecture

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-017 |
| Title | Local-First and Cloud Migration Architecture |
| Version | 0.1.0 |
| Status | Draft (Foundation Skeleton) |
| Project | DarkSage |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated. Structural skeleton only. Does not alter DS-001–DS-014.

Parent: [DS-001 — Executive Vision & Product Foundation](../Volume-01-Foundation/DS-001-Executive-Vision.md).

## 1. Purpose

Define how DarkSage's local-first operating model (the Founder Workstation's principal mode today) extends into a customer-facing product that may run locally, in the cloud, or migrate between the two — without ever silently changing which system is authoritative for a given piece of data.

## 2. Scope

- Local-first operation guarantees (what must keep working with no network connection).
- Provider abstraction boundaries (market data, broker, Sage) that make local/cloud substitution safe.
- Offline and degraded-mode behavior contracts.
- Synchronization model between a local instance and a cloud-hosted account.
- Conflict-resolution rules when local and cloud state diverge.
- Local→cloud (and cloud→local) migration mechanics.
- Backup foundation (this volume defines the *architecture*; DS-023 owns operational backup/recovery procedures).

## 3. Non-Goals

- Does not define disaster-recovery SLOs or incident response procedures — that is DS-023.
- Does not define Sage's local/cloud routing specifically — that is DS-018 (this volume covers data/provider architecture generally; DS-018 covers Sage's own hybrid design).
- Does not weaken DS-001's local-first principle; cloud is an additive deployment option, not a replacement requirement.

## 4. Owner Requirement Families

- **DS-LOC** (new, proposed) — Local-First Architecture. Primary volume: DS-017.

## 5. Supporting Requirement Families

- DS-ARC (DS-004) — provider-abstraction and deployment architecture this volume extends.
- DS-DAT (DS-002) — data-management/retention requirements a migration must preserve.
- DS-DB (DS-005) — schema/storage implications of local vs. cloud persistence.

## 6. Dependencies

- DS-004 (Technical Architecture) — existing provider-abstraction patterns (market data, broker) this volume must extend consistently, not duplicate.
- DS-018 (Sage Deployment) — Sage's hybrid local/cloud design depends on this volume's general local/cloud data architecture.
- DS-023 (Reliability, Operations, Data Governance, and Recovery) — backup/recovery *operations* built on this volume's *architecture*.

## 7. Major Sections (Planned for Full Draft)

1. Local-First Operating Guarantees
2. Provider Abstraction Boundaries
3. Offline/Degraded-Mode Contracts
4. Synchronization Model
5. Conflict Resolution Rules
6. Local↔Cloud Migration Mechanics
7. Backup Architecture Foundation (handoff to DS-023 for operations)

## 8. Cross-Volume References

- DS-004 (Technical Architecture), DS-005 (Database Design), DS-018 (Sage Deployment and Intelligence Architecture), DS-019 (Commercialization — cloud hosting cost/entitlement interplay), DS-023 (Reliability, Operations, Data Governance, and Recovery).

## 9. Acceptance Criteria (Placeholders)

- [ ] Every provider abstraction has a documented offline/degraded behavior, not merely a "works when online" assumption.
- [ ] A local→cloud migration never silently loses or duplicates data; conflict resolution is deterministic and disclosed to the user.
- [ ] No cloud dependency is introduced into a capability that DS-001 requires to work fully offline.

## 10. Traceability (Placeholders)

- [ ] DS-LOC-001 … (allocated in `docs/features/FEATURE_GOVERNANCE.md`; full requirement text deferred).

## 11. Release-Stage Responsibilities

| Stage | Responsibility |
|---|---|
| Stage 1 | Local-first operation is the only mode; provider abstractions designed with future cloud substitution in mind. |
| Stage 3 (Founder Workstation Beta) | Local-first guarantees proven under real daily Founder use. |
| Stage 4 (Customer Cloud Beta) | Cloud deployment path and synchronization model enter beta. |
| Stage 5 (Initial Commercial Release) | Local↔cloud migration is a supported, tested customer path. |

## 12. Open Decisions

- Whether customers are ever offered a true "fully local, no cloud account" tier, or cloud account is mandatory for the Customer Edition.
- Conflict-resolution policy default (last-write-wins vs. explicit user reconciliation) — deferred to full draft.

## 13. Known Risks

- Synchronization/conflict-resolution defects are a classic source of silent data loss; this volume's acceptance criteria treat that as a Critical-severity class of defect once fully drafted.
- Underestimating offline-mode scope could make a "local-first" claim inaccurate in practice.
