# The DarkSage Codex

The Codex is the authoritative engineering documentation system for DarkSage.

## Source-of-Truth Rule

- Markdown files are authoritative for engineering work.
- Word documents are polished human-facing editions.
- When the two differ, update Markdown first and regenerate Word.

## Status Workflow

`Draft → Under Review → Approved → Superseded/Deprecated`

- **Superseded:** replaced by a newer authoritative document or version.
- **Deprecated:** retained for historical or reference purposes but no longer recommended or current.

## Versioning

Codex documents use semantic versioning:

- Major: structural or policy-breaking change
- Minor: approved expansion
- Patch: correction or clarification

## Core Policy

Major features must be documented before implementation.

## Foundation Completion Release — 2026-07-25

The Core Codex remains DS-001 through DS-014. This release repairs cross-volume vision and authority gaps before creation of DS-015+ specialized volumes. It adds bounded Sage agency, canonical Trade Intelligence Packages, Research Intelligence, Journal & Review Intelligence, live-workstation requirements, stronger education/portfolio/strategy direction, five-mode automation reconciliation, and opt-in Discord alerts with a notification-only security boundary.

See `RELEASE_NOTES_2026-07-25_FOUNDATION_COMPLETION.md` and `RELEASE_MANIFEST_2026-07-25.json`.

## Product Expansion Foundation — 2026-07-25 (Draft, Not Yet Approved)

The Core Codex (DS-001 through DS-014, commit `1e48041fb59593b3bc62c490e3bb60d343287a15`) is locked, independently verified, and unaltered by this section. This foundation pass adds nine new **Product Expansion** volumes, each currently a structural skeleton (Draft, Version 0.1.0) pending full drafting, plus the **Complete Features System** under `docs/features/` (master catalog, machine-readable registry, and supporting matrices covering release stages, platforms, editions, dependencies, timelines, and TradingView-capability classification).

| Volume | Title | Status |
|---|---|---|
| [DS-015](Volume-15-Editions/DS-015-Product-Editions-and-Repository-Architecture.md) | Product Editions and Repository Architecture | Draft (Skeleton) |
| [DS-016](Volume-16-Platforms/DS-016-Platform-Strategy-and-Distribution.md) | Platform Strategy and Distribution | Draft (Skeleton) |
| [DS-017](Volume-17-LocalFirst/DS-017-Local-First-and-Cloud-Migration-Architecture.md) | Local-First and Cloud Migration Architecture | Draft (Skeleton) |
| [DS-018](Volume-18-SageDeployment/DS-018-Sage-Deployment-and-Intelligence-Architecture.md) | Sage Deployment and Intelligence Architecture | Draft (Skeleton) |
| [DS-019](Volume-19-Commercialization/DS-019-Commercialization-Subscriptions-and-Entitlements.md) | Commercialization, Subscriptions, and Entitlements | Draft (Skeleton) |
| [DS-020](Volume-20-MultiUser/DS-020-Multi-User-Multi-Account-Trading-Controls-and-Delegated-Access.md) | Multi-User, Multi-Account, Trading Controls, and Delegated Access | Draft (Skeleton) |
| [DS-021](Volume-21-SecurityDeviceTrust/DS-021-Security-Device-Trust-Privacy-and-IP-Protection.md) | Security, Device Trust, Privacy, and Intellectual-Property Protection | Draft (Skeleton) |
| [DS-022](Volume-22-ProductExperience/DS-022-Product-Experience-Website-Design-System-and-Feature-Governance.md) | Product Experience, Website, Design System, and Feature Governance | Draft (Skeleton) |
| [DS-023](Volume-23-Reliability/DS-023-Reliability-Operations-Data-Governance-and-Recovery.md) | Reliability, Operations, Data Governance, and Recovery | Draft (Skeleton) |

See `../features/DARKSAGE_COMPLETE_FEATURES.md` for the master feature catalog and `../features/FEATURE_GOVERNANCE.md` for the controlled-ID family registry (including collision resolutions against existing DS-002/DS-007 families) governing this expansion.

A new launch readiness and publication state package has been added under `../launch/` and `../publication/` to track readiness gates, legal and billing artifacts, product analytics, transactional email requirements, and the publication lifecycle for DS-001 through DS-023.
