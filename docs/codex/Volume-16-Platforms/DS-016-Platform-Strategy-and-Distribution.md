# DS-016 — Platform Strategy and Distribution

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-016 |
| Title | Platform Strategy and Distribution |
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

Define which platforms DarkSage supports at each release stage, how each platform is packaged and distributed, and the compatibility/release-channel model that keeps platform expansion from silently becoming a scope or security liability.

## 2. Scope

- Supported platforms per stage: Windows desktop (primary), web account/dashboard, iOS, Android, and future macOS/Linux.
- Packaging and distribution mechanics (installer, app-store submission, auto-update channel) per platform.
- Browser/device compatibility baseline for the web surface.
- Release channels (e.g. stable/beta/internal) and their relationship to release stages (Stage 0–9).
- The Platform Capability Matrix (`docs/features/PLATFORM_CAPABILITY_MATRIX.csv`) as the canonical record of which feature is available on which platform.

## 3. Non-Goals

- Does not define feature scope itself (that lives in the Complete Features System and each feature's owning volume) — only *where* an already-authorized feature is allowed to run.
- Does not define edition boundaries (DS-015) or entitlement/subscription mechanics (DS-019).
- Does not commit to a Linux or macOS release date; both remain groundwork-tracked, not scheduled, until explicitly promoted.

## 4. Owner Requirement Families

- **DS-PLT** (new, proposed) — Platforms. Primary volume: DS-016.

## 5. Supporting Requirement Families

- DS-MOB (existing, DS-002/Volume-02-Product/requirements/DS-MOB-Mobile-Client.md) — mobile-client product requirements this volume's platform/distribution rules must fit.
- DS-ARC (DS-004) — architecture constraints on multi-platform clients sharing a backend-authoritative API.
- DS-NFR (DS-002) — non-functional/performance baselines per platform.

## 6. Dependencies

- DS-015 (Editions) — platform builds must respect edition boundaries.
- DS-006 (API Specification) — every platform client is a consumer of the same backend-authoritative API (DS-API-COR family); no platform-specific bypass of deterministic validation.
- DS-019 (Commercialization) — app-store billing/entitlement interplay.

## 7. Major Sections (Planned for Full Draft)

1. Platform Tier Definitions (Primary / Companion / Future)
2. Packaging and Distribution per Platform
3. Release Channel Model
4. Browser/Device Compatibility Baseline (Web)
5. Linux/macOS Packaging Groundwork (explicitly deferred, not scheduled)
6. Platform Parity Policy (what must be identical vs. what may legitimately differ across platforms)

## 8. Cross-Volume References

- DS-002 (DS-MOB), DS-004 (Technical Architecture), DS-006 (API Specification), DS-015 (Editions), DS-019 (Commercialization), DS-021 (Device Trust).

## 9. Acceptance Criteria (Placeholders)

- [ ] Every feature in `FEATURE_REGISTRY.csv` has a resolvable, non-empty `platform_availability` value.
- [ ] No platform client bypasses the backend-authoritative deterministic validation pipeline (DS-ARC-011 / DS-API-EXE-001).
- [ ] Linux packaging compatibility is documented as Groundwork Required Now even though no Linux release is scheduled.

## 10. Traceability (Placeholders)

- [ ] DS-PLT-001 … (allocated in `docs/features/FEATURE_GOVERNANCE.md`; full requirement text deferred).
- [ ] Cross-reference table linking DS-PLT-NNN → `PLATFORM_CAPABILITY_MATRIX.csv` rows — TODO.

## 11. Release-Stage Responsibilities

| Stage | Responsibility |
|---|---|
| Stage 1–2 | Windows desktop only; no distribution packaging yet beyond internal builds. |
| Stage 3 (Founder Workstation Beta) | Windows desktop packaging hardened for daily Founder use. |
| Stage 4 (Customer Cloud Beta) | Web account/dashboard and mobile companion apps (iOS, Android) enter beta distribution. |
| Stage 5 (Initial Commercial Release) | Windows desktop, web, iOS, Android all reach general-availability distribution channels. |
| Stage 7 | macOS/Linux packaging groundwork may be promoted from backlog if justified by demand. |

## 12. Open Decisions

- Whether macOS ever becomes a primary platform or remains long-term backlog.
- Exact mobile app-store review/compliance strategy for a trading-adjacent app (varies by store policy).

## 13. Known Risks

- App-store policy changes for financial-trading apps could block or delay mobile distribution.
- Supporting too many platforms too early could dilute Founder attention away from the deterministic core the whole system depends on.
