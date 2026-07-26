# DS-015 — Product Editions and Repository Architecture

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-015 |
| Title | Product Editions and Repository Architecture |
| Version | 0.1.0 |
| Status | Draft (Foundation Skeleton) |
| Project | DarkSage |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated. This document is a **structural skeleton only** — section content is placeholder scaffolding pending full drafting in a later pass, per the Product Expansion foundation instructions. No section here overrides or amends DS-001 through DS-014, which remain the locked, independently-verified Core Codex baseline (commit `1e48041fb59593b3bc62c490e3bb60d343287a15`).

Parent: [DS-001 — Executive Vision & Product Foundation](../Volume-01-Foundation/DS-001-Executive-Vision.md). Part of the Product Expansion volume set (DS-015 through DS-023), which extends but does not alter the Core Codex.

## 1. Purpose

Define the boundary between the **Founder Edition** (private, single-operator, full-capability workstation build) and the **Customer Edition** (multi-tenant, commercially distributed build), and the repository/build architecture that makes that boundary structurally enforceable rather than merely policy-enforced — so a Founder-only asset (e.g. Founder Local Sage, private research tooling) can never ship inside a customer build by omission or human error.

## 2. Scope

- Edition definitions (Founder Edition, Customer Edition) and what capability set each includes.
- Repository/monorepo boundary structure separating Founder-only code/assets from customer-shippable code.
- Build-time exclusion mechanism(s) that keep Founder-only assets out of any customer artifact.
- Shared-contract surface (APIs, schemas, deterministic services) both editions depend on identically.
- The Edition Capability Matrix (`docs/features/EDITION_CAPABILITY_MATRIX.csv`) as the canonical, machine-checkable record of which feature belongs to which edition.

## 3. Non-Goals

- Does not define subscription tiers, billing, trials, or entitlement quotas within the Customer Edition — that is DS-019's scope.
- Does not define platform packaging (installers, app-store distribution) — that is DS-016's scope.
- Does not weaken, reinterpret, or re-scope any DS-001–DS-014 requirement.
- Does not authorize any new customer-facing feature by itself; features are authorized via the Complete Features System (`docs/features/`) and their owning requirement volume.

## 4. Owner Requirement Families

- **DS-EDN** (new, proposed) — Editions. Primary volume: DS-015.

## 5. Supporting Requirement Families

- DS-ARC (DS-004 — Technical Architecture) — repository/build architecture patterns this volume must fit within.
- DS-SGE (DS-003 — Sage AI Bible) — Founder Local Sage is the paradigm case of a Founder-only asset this volume's build-exclusion mechanism must protect.
- DS-SCA (DS-008 — Security Architecture) — protected-asset classification for Founder-only code/data.

## 6. Dependencies

- DS-001 §9 (restraint principle), DS-001's Founder/customer distinction (already established at the vision level).
- DS-004 (Technical Architecture) for the concrete repository/build-pipeline mechanics this volume constrains.
- DS-016 (Platform Strategy) for how edition boundaries interact with per-platform packaging.
- DS-019 (Commercialization) for how editions interact with entitlements/subscriptions.

## 7. Major Sections (Planned for Full Draft)

1. Edition Definitions (Founder Edition, Customer Edition)
2. Repository Boundary Model
3. Build-Time Exclusion Mechanism
4. Shared Contract Surface
5. Edition Capability Matrix Governance
6. Edition Promotion/Downgrade Rules (if any content ever moves from Founder-only to Customer-available)
7. Verification: How CI Proves No Founder Asset Leaked Into a Customer Build

## 8. Cross-Volume References

- DS-004 (Technical Architecture), DS-008 (Security Architecture), DS-016 (Platform Strategy and Distribution), DS-018 (Sage Deployment and Intelligence Architecture), DS-019 (Commercialization, Subscriptions, and Entitlements), DS-022 (Product Experience — Edition Capability Matrix consumer).

## 9. Acceptance Criteria (Placeholders)

- [ ] Every feature in `FEATURE_REGISTRY.csv` has a resolvable, non-empty `edition_availability` value.
- [ ] No Founder-only capability appears in the Customer Edition's build output (verified mechanically, not by review alone).
- [ ] The repository boundary model is testable in CI (a build attempted with customer-only inputs cannot produce a Founder-tagged artifact).

## 10. Traceability (Placeholders)

- [ ] DS-EDN-001 … (allocated in `docs/features/FEATURE_GOVERNANCE.md`'s controlled-ID family registry; full requirement text deferred to full-draft pass).
- [ ] Cross-reference table linking DS-EDN-NNN → owning feature_id(s) in `FEATURE_REGISTRY.csv` — TODO.

## 11. Release-Stage Responsibilities

| Stage | Responsibility |
|---|---|
| Stage 0 | This skeleton; edition concept ratified at documentation level. |
| Stage 1 | Repository boundary and build-exclusion mechanism designed and prototyped. |
| Stage 3 (Founder Workstation Beta) | Founder Edition build is the *only* build in active use; boundary mechanism exercised daily by construction. |
| Stage 4 (Customer Cloud Beta) | Customer Edition build must exist and be provably Founder-asset-free. |
| Stage 5 (Initial Commercial Release) | Edition Capability Matrix fully populated and enforced in CI for every release artifact. |

## 12. Open Decisions

- Whether a third edition tier (e.g. an internal "Staff/QA Edition") is ever needed, or whether Founder/Customer is a permanently closed two-edition model.
- Exact build-exclusion mechanism (separate build target vs. feature-flag stripping vs. separate repository/submodule) — architectural decision deferred to full DS-015 draft in coordination with DS-004.

## 12a. Founder Sage Developer Mode (`FEAT-0268`) — Edition/Repository Boundary, Added 2026-07-26

**Status:** structural skeleton only, not a full requirement draft. DS-015 supports the edition/repository boundary for this Founder-only capability; DS-018 is its primary owner (see DS-018 §14).

- Founder Sage Developer Mode is bound by the same Founder-only edition boundary as Founder Local Sage: it exists only in the Founder Edition build and is **excluded from every customer build** by the same build-time exclusion mechanism (§7.3) this volume defines.
- Its private assets — repository access, local coding-model weights/prompts, and development tooling — are Founder-private assets under this volume's scope, on the same footing as Founder Local Sage's model weights.
- **Shared-core interfaces versus Founder-private implementation:** any interface Developer Mode uses that also serves customer-facing code (e.g. a shared API contract) remains shared/customer-shippable; the Developer Mode implementation itself (coding-model routing, sandboxed tool execution, commit-preparation logic) is Founder-private and never crosses into a customer artifact.
- Release verification (§7.7, "Verification: How CI Proves No Founder Asset Leaked Into a Customer Build") must include Developer Mode's assets in its Founder-only-marker scan.
- **No customer entitlement, tier, or subscription plan can enable Developer Mode.** It is not part of the Customer Edition's capability set at any tier, now or by future entitlement expansion, without a separate, explicit edition-boundary decision.
- No Founder credential, coding-model prompt, or Developer Mode configuration may appear in any customer-distributed artifact.

## 13. Known Risks

- **High-consequence, low-probability risk:** a misconfigured build step silently includes a Founder-only asset in a customer artifact. Mitigation (to be fully specified in full draft): CI gate that scans every customer build artifact for Founder-only markers before release.
- Edition boundary drawn too rigidly could block legitimate future upsell (e.g. a premium customer tier wanting a Founder-adjacent capability) — to be resolved via DS-019 entitlement design, not by weakening this volume's boundary.
