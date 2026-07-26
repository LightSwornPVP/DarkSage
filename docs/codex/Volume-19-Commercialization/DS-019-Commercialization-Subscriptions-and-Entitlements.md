# DS-019 — Commercialization, Subscriptions, and Entitlements

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-019 |
| Title | Commercialization, Subscriptions, and Entitlements |
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

Define how the Customer Edition is commercialized: subscription tiers, billing, trials, grace-mode behavior when payment lapses, cancellation, entitlement quotas (including Sage usage quotas whose architecture DS-018 owns), regional commercial restrictions, and customer account administration.

## 2. Scope

- Subscription tier definitions and what each tier entitles.
- Billing and payment-provider integration boundary (architecture-level; specific vendor selection deferred).
- Trial period mechanics.
- Grace mode: behavior when a subscription lapses (what degrades, what remains available, e.g. read-only journal/portfolio access).
- Cancellation and data-export-on-cancellation guarantees (consistent with DS-DAT-004's data-minimization/export principles).
- Entitlement quotas (Sage usage, alert volume, watchlist counts, etc. — values, not architecture; DS-018 owns Sage's quota architecture).
- Regional commercial restrictions (jurisdictions where DarkSage is not offered, or offered with restrictions).
- Customer account administration (plan changes, seat/account management at the individual-customer level — not multi-user workspace roles, which is DS-020).

## 3. Non-Goals

- Does not define multi-user/multi-account *trading* controls or delegated approvals — DS-020.
- Does not define Sage's deployment architecture — DS-018 (this volume only sets quota *values*).
- Does not define platform-specific billing mechanics (e.g. app-store in-app-purchase specifics) beyond the general entitlement model — DS-016 covers platform distribution; in-app-purchase implementation detail is deferred to full draft.

## 4. Owner Requirement Families

- **DS-SUB** (new, proposed) — Subscriptions. Primary volume: DS-019.
- **DS-ENT** (new, proposed) — Entitlements. Primary volume: DS-019.

## 5. Supporting Requirement Families

- DS-DAT (DS-002) — data-export/retention obligations on cancellation.
- DS-USR (DS-002) — account/onboarding requirements this volume extends commercially.
- DS-018 (Sage Deployment) — Sage quota architecture this volume assigns values against.

## 6. Dependencies

- DS-015 (Editions) — subscriptions apply only within the Customer Edition.
- DS-016 (Platform Strategy) — app-store billing interplay per platform.
- DS-020 (Multi-User) — account-level entitlements vs. workspace-level roles boundary.

## 7. Major Sections (Planned for Full Draft)

1. Subscription Tier Definitions
2. Billing and Payment-Provider Integration Boundary
3. Trial Mechanics
4. Grace Mode
5. Cancellation and Data Export
6. Entitlement Quota Catalog
7. Regional Commercial Restrictions
8. Customer Account Administration

## 8. Cross-Volume References

- DS-002 (DS-DAT, DS-USR), DS-015 (Editions), DS-016 (Platform Strategy and Distribution), DS-018 (Sage Deployment and Intelligence Architecture), DS-020 (Multi-User, Multi-Account, Trading Controls, and Delegated Access).

## 9. Acceptance Criteria (Placeholders)

- [ ] Every subscription tier has an explicit entitlement list; no tier is defined only by exclusion.
- [ ] Grace mode never silently deletes user data; only restricts new activity until resolved.
- [ ] Cancellation always offers data export before any data becomes inaccessible.

## 10. Traceability (Placeholders)

- [ ] DS-SUB-001 …, DS-ENT-001 … (allocated in `docs/features/FEATURE_GOVERNANCE.md`; full requirement text deferred).

## 11. Release-Stage Responsibilities

| Stage | Responsibility |
|---|---|
| Stage 4 (Customer Cloud Beta) | Subscription/billing/trial mechanics enter beta; grace mode designed and tested. |
| Stage 5 (Initial Commercial Release) | Full subscription, entitlement, and regional-restriction model live. |

## 12. Open Decisions

- Number and shape of subscription tiers (single tier vs. multiple) — deferred to full draft and business decision.
- Whether any capability is ever offered as a one-time purchase rather than subscription-only.

## 13. Known Risks

- Billing defects (double-charging, failed grace-mode transitions) are high-trust-impact; full draft must treat them as release-blocking defect classes.
- Regional commercial-restriction gaps could create regulatory exposure if not comprehensively enumerated before Stage 5.
