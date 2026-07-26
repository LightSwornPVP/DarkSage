# DS-022 — Product Experience, Website, Design System, and Feature Governance

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-022 |
| Title | Product Experience, Website, Design System, and Feature Governance |
| Version | 0.1.0 |
| Status | Draft (Foundation Skeleton) |
| Project | DarkSage |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated. Structural skeleton only. Does not alter DS-001–DS-014, and in particular does not reinterpret DS-007 (UI/UX Bible)'s existing DS-UX-NNN requirements.

Parent: [DS-007 — UI/UX System](../Volume-07-UX/DS-007-UI-UX-Bible.md).

## 1. Purpose

Own the **Complete Features System** (`docs/features/`) as governance infrastructure, the public website, and the cross-platform product-experience layer (desktop/mobile/web UX not already covered by DS-007's existing scope), the design system, accessibility, TradingView capability classification, and feature lifecycle rules — while DS-007 remains the sole authority for its own existing DS-UX-NNN requirements.

## 2. Scope

- The Complete Features System: master catalog, feature registry, and all supporting matrices under `docs/features/`.
- Feature lifecycle governance: status values, transition rules, evidence requirements, ownership rules (one primary owner, multiple supporting owners).
- Public website (marketing/informational site, distinct from the authenticated web account/dashboard which DS-016 covers as a platform).
- Morning Brief and Needs My Attention: cross-platform product-experience surfaces.
- Onboarding, command palette, progressive disclosure — UX patterns extending DS-007.
- Design system and accessibility (extending DS-007's existing WCAG 2.2 AA commitments to the expanded feature surface).
- TradingView capability classification (`docs/features/TRADINGVIEW_CAPABILITY_COMPARISON.md`) as this volume's governance artifact.
- Charting, drawing tools, screeners, watchlists, market visualization, market calendars, and creator/ecosystem *feature-family stewardship* in this foundation pass (see §4 — final requirement authorship for some of these may ultimately live in DS-002, to be confirmed when each family is fully drafted).

## 3. Non-Goals

- Does not redefine or weaken any existing DS-UX-NNN requirement owned by DS-007; new product-experience requirements in the expansion scope use the existing DS-UX family (reused, not duplicated) or this volume's own new families where the concept is genuinely new.
- Does not own subscription/billing UX specifics beyond presentation — DS-019 owns the underlying entitlement logic.
- Does not itself authorize any feature; it governs *how* features are tracked, not which are approved.

## 4. Owner Requirement Families

- **DS-DSN** (new, proposed) — Design System. Primary volume: DS-022.
- **DS-FTR** (new, proposed) — Feature Governance. Primary volume: DS-022.
- **DS-DRW** (new, proposed) — Drawing Tools. Primary volume: DS-022 (stewardship in this foundation pass; final home to be confirmed with DS-002 in full draft).
- **DS-SCR** (new, proposed) — Screeners. Primary volume: DS-022 (stewardship; see Open Decisions re: relationship to existing DS-SCN).
- **DS-WCH** (new, proposed) — Watchlists. Primary volume: DS-022 (stewardship).
- **DS-VIZ** (new, proposed; renamed from the initially-suggested "DS-MKT" to avoid collision with the existing DS-MKT/Market-Data family) — Market Visualization. Primary volume: DS-022 (stewardship).
- **DS-CAL** (new, proposed) — Market Calendars. Primary volume: DS-022 (stewardship).
- **DS-ECO** (new, proposed) — Creator and Ecosystem Features. Primary volume: DS-022 (stewardship).
- **DS-UX** (existing, DS-007) — reused, not duplicated; DS-022 is a supporting/cross-referencing volume for expansion-scope product-experience requirements filed under the existing family.

## 5. Supporting Requirement Families

- DS-CHT (existing, DS-002) — reused for charting-expansion requirements; DS-022 cross-references for UX presentation.
- DS-STR (existing, DS-002) — reused for strategy-customization requirements (visual builder, indicator builder); DS-022 cross-references for UX presentation.
- DS-ALT (existing, DS-002) — reused for alert-expansion requirements; DS-022 cross-references for UX presentation.

## 6. Dependencies

- DS-007 (UI/UX System) — existing design/accessibility authority this volume extends, never overrides.
- DS-002 (DS-CHT, DS-STR, DS-ALT, DS-SCN) — existing requirement families this volume's stewarded new families (DS-DRW, DS-SCR, DS-WCH, DS-VIZ, DS-CAL, DS-ECO) must eventually reconcile with in full draft.
- DS-015 (Editions) — Edition Capability Matrix consumer.
- DS-016 (Platforms) — Platform Capability Matrix consumer.

## 7. Major Sections (Planned for Full Draft)

1. Complete Features System Governance (statuses, stages, evidence, ownership rules)
2. Public Website
3. Morning Brief and Needs My Attention
4. Onboarding, Command Palette, Progressive Disclosure
5. Design System and Accessibility Extension
6. TradingView Capability Classification Governance
7. Charting/Drawing/Screener/Watchlist/Visualization/Calendar/Ecosystem Family Stewardship (pending full-draft ownership confirmation with DS-002)

## 8. Cross-Volume References

- DS-002 (DS-CHT, DS-STR, DS-ALT, DS-SCN), DS-007 (UI/UX System), DS-015 (Editions), DS-016 (Platform Strategy and Distribution), all of DS-015–DS-023 (as the Complete Features System governance owner, this volume cross-references every expansion volume).

## 9. Acceptance Criteria (Placeholders)

- [ ] Every feature in `FEATURE_REGISTRY.csv` has exactly one primary `owner_volume`; supporting volumes may be multiple.
- [ ] Every TradingView-comparable capability listed in the foundation instructions appears in `TRADINGVIEW_CAPABILITY_COMPARISON.md` with a classification (A–E).
- [ ] No feature status is asserted without the evidence class its status requires (see `FEATURE_STATUS_DEFINITIONS.md`).

## 10. Traceability (Placeholders)

- [ ] DS-DSN-001 …, DS-FTR-001 …, DS-DRW-001 …, DS-SCR-001 …, DS-WCH-001 …, DS-VIZ-001 …, DS-CAL-001 …, DS-ECO-001 … (allocated in `docs/features/FEATURE_GOVERNANCE.md`; full requirement text deferred).

## 11. Release-Stage Responsibilities

| Stage | Responsibility |
|---|---|
| Stage 0 | Complete Features System foundation (this pass) exists and is internally consistent. |
| Stage 2–3 | Core charting/watchlist/alert UX matures for Founder daily use, per existing DS-007/DS-UX requirements. |
| Stage 5 (Initial Commercial Release) | Design system and accessibility baseline apply uniformly across desktop/web/mobile; public website live. |
| Stage 7 (Platform and TradingView-Style Expansion) | Drawing-tool, screener, and market-visualization families mature toward broader TradingView-comparable coverage per the groundwork already laid. |

## 12. Open Decisions

- Whether DS-SCR (Screeners) ultimately merges into, or remains distinct from, the existing DS-SCN (Scanner/Watchtower) family — DS-SCN is an automated candidate-generation pipeline; DS-SCR as proposed is a user-driven, TradingView-style ad-hoc filter tool. Relationship requires product-authority clarification before full draft.
- Final permanent requirement-ownership home for DS-DRW/DS-SCR/DS-WCH/DS-VIZ/DS-CAL/DS-ECO (remain under DS-022 long-term, or migrate into DS-002 alongside the other product-requirement families) — deferred to full-draft decision.

## 13. Known Risks

- Governing a large, fast-growing feature catalog without disciplined ownership rules risks exactly the kind of drift the Core Codex just spent two repair cycles fixing (stale counts, conflicting classifications) — this volume's validators (see `docs/features/FEATURE_GOVERNANCE.md`) exist specifically to prevent repeating that failure mode at expansion scale.
- Naming collisions between newly-proposed families and existing DS-002 families (DS-CHT, DS-STR, DS-ALT, DS-UX, and the avoided DS-MKT collision) require careful, continued discipline as more families are proposed in future expansion passes.
