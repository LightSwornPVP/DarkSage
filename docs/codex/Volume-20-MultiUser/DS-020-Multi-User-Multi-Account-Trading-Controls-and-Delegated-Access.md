# DS-020 — Multi-User, Multi-Account, Trading Controls, and Delegated Access

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-020 |
| Title | Multi-User, Multi-Account, Trading Controls, and Delegated Access |
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

Define multi-user workspaces, multi-account trading, roles/permissions, delegated approval workflows, and the stop-loss/take-profit/kill-switch control surface — always preserving DS-001/ADR-002's principle that deterministic risk validation is independent per account and is never bypassed by a role, a delegated approval, or a remote/mobile control action.

## 2. Scope

- Multi-user workspaces: roles, permissions, and how they compose with the single-user model DS-001–014 already assume.
- Multi-account trading: an authenticated user operating more than one brokerage/paper account, each independently risk-validated.
- Delegated approvals: one user authorizing another (or an automation) to act within explicit, revocable, scoped limits.
- Stop loss and take profit feature family (fixed-price, percentage, ATR/volatility, trailing, break-even, time-based, multi-target, scale-out) — primary owner of the **DS-EXT** family.
- Kill switches: global, account-level, broker-level, and strategy-level — including mobile remote kill-switch controls.
- Account-specific risk configuration and independent per-account validation (no cross-account risk aggregation silently overriding an individual account's own limits without explicit design).
- Broadcast preparation: architecture allowing one action to be *proposed* across multiple accounts, while each account's deterministic validation still runs independently and can independently reject.

## 3. Non-Goals

- Does not define subscription/entitlement mechanics for multi-account access — DS-019.
- Does not define the underlying single-account deterministic risk engine itself (DS-002 DS-RSK, DS-004 DS-ARC-011 TradeValidationPipeline) — this volume *composes* multiple independent instances of that existing authority, never replaces or bypasses it.
- Does not permit any role or delegation to grant execution authority that skips the TradeValidationPipeline.

## 4. Owner Requirement Families

- **DS-MUA** (new, proposed) — Multi-User/Multi-Account. Primary volume: DS-020.
- **DS-EXT** (new, proposed) — Stop-Loss, Take-Profit, and Exit Management. Primary volume: DS-020. Deliberately distinct from the existing **DS-EXE** family (DS-002 — Execution and Broker), which owns order-execution/broker-integration requirements generally; DS-EXT is scoped specifically to exit-plan/protective-order logic.

## 5. Supporting Requirement Families

- DS-RSK (DS-002) — deterministic risk engine this volume's multi-account model must independently invoke per account.
- DS-EXE (DS-002) — broker/execution integration this volume's exit orders (brackets, OCO, trailing stops) route through.
- DS-MOB (DS-002) — mobile kill-switch controls.
- DS-PRT (DS-002) — portfolio/account structures this volume extends to multiple accounts.

## 6. Dependencies

- ADR-002 (Sage Cannot Bypass the Risk Engine) — extended here to "no role, delegation, or remote control bypasses the Risk Engine either."
- DS-004 (DS-ARC-011, TradeValidationPipeline) — the single authority every account's proposal still passes through independently.
- DS-019 (Commercialization) — multi-account access as a possible entitlement tier.
- DS-021 (Security, Device Trust) — delegated-access authentication/authorization mechanics.

## 7. Major Sections (Planned for Full Draft)

1. Multi-User Workspace and Role Model
2. Multi-Account Trading Architecture
3. Delegated Approval Workflow
4. Stop-Loss and Take-Profit Feature Catalog (DS-EXT)
5. Kill Switch Hierarchy (Global / Account / Broker / Strategy)
6. Mobile Remote Trading Controls
7. Account-Specific Risk Configuration
8. Broadcast Preparation and Independent Per-Account Validation

## 8. Cross-Volume References

- DS-002 (DS-RSK, DS-EXE, DS-MOB, DS-PRT), DS-004 (Technical Architecture), DS-019 (Commercialization), DS-021 (Security, Device Trust, Privacy, and IP Protection).

## 9. Acceptance Criteria (Placeholders)

- [ ] Every multi-account action is independently validated by the deterministic Risk Engine per account; no aggregate/broadcast action can bypass a single account's own rejection.
- [ ] Every delegated approval is explicit, scoped, and revocable; no implicit or silent delegation exists.
- [ ] Every automated entry has an associated, approved deterministic exit plan (per the Stop Loss and Take Profit requirement below), and Sage may recommend but never approve or bypass that validation.
- [ ] Kill switches at every level (global/account/broker/strategy) are tested to actually halt new order submission, not merely flagged as halted in the UI.

## 10. Traceability (Placeholders)

- [ ] DS-MUA-001 …, DS-EXT-001 … (allocated in `docs/features/FEATURE_GOVERNANCE.md`; full requirement text deferred).

## 11. Release-Stage Responsibilities

| Stage | Responsibility |
|---|---|
| Stage 3 (Founder Workstation Beta) | Single-account model remains authoritative; multi-account/multi-user architecture designed but not required for Founder's own use. |
| Stage 5 (Initial Commercial Release) | Stop loss, take profit, bracket/OCO orders, trailing stops, break-even stops, partial exits, multi-target exits, and mobile kill switches are release-required (see Complete Features System, category "Initial Release Boundary"). |
| Stage 6 (Advanced Trading Expansion) | Full multi-user workspaces, delegated approvals, and multi-account broadcast preparation mature incrementally. |

## 12. Open Decisions

- Whether delegated approval ever permits a delegate to *place* an order versus only *propose* one for the account owner's confirmation — leaning toward propose-only at launch, to be confirmed in full draft.
- Cross-account risk aggregation policy (informational only vs. enforceable) — deferred.

## 13. Known Risks

- A kill switch that appears to work in the UI but does not actually halt backend order submission would be a Critical-severity defect once implemented; full draft must specify a hard test requirement for this.
- Delegated access is a natural attack surface for account takeover; DS-021 collaboration is mandatory before any delegated-approval feature ships.
