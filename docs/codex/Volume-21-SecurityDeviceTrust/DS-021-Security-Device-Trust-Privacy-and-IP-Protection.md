# DS-021 — Security, Device Trust, Privacy, and Intellectual-Property Protection

## Document Control

| Field | Value |
|---|---|
| Document ID | DS-021 |
| Title | Security, Device Trust, Privacy, and Intellectual-Property Protection |
| Version | 0.1.0 |
| Status | Draft (Foundation Skeleton) |
| Project | DarkSage |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated. Structural skeleton only. Does not alter DS-001–DS-014, and in particular does not reinterpret DS-008 (Security Architecture)'s existing DS-SCA-NNN controls.

Parent: [DS-008 — Security Architecture](../Volume-08-Security/DS-008-Security-Architecture.md).

## 1. Purpose

Extend DS-008's security architecture into the product-expansion surface: multi-device trust for a multi-user/multi-account world, MFA, secret management for distributed clients, and — distinctly — intellectual-property protection for Founder-private assets (code, models, research methodology) against extraction, reverse-engineering, or leakage through a distributed customer product.

## 2. Scope

- Device trust model: registering, verifying, and revoking trusted devices across desktop/web/mobile.
- Multi-factor authentication for customer accounts (extending beyond DS-008's existing baseline where the multi-user/multi-account surface requires it).
- Secret management for distributed clients (never embedding secrets in a shipped customer client, per existing DS-SEC-001 principle).
- Intellectual-property protection: code signing, attestation, and revocation mechanisms protecting Founder-only assets from extraction via a customer build.
- Incident security response specific to the expanded, multi-tenant attack surface (informing, not duplicating, DS-023's operational incident center).

## 3. Non-Goals

- Does not redefine DS-008's existing protected-asset catalog (DS-SCA-023) or data-protection controls (DS-SCA-028) — this volume extends coverage to new multi-device/multi-tenant scenarios, it does not restate or weaken what DS-008 already governs.
- Does not own operational incident response procedures generally — DS-023.

## 4. Owner Requirement Families

- **DS-DVT** (new, proposed) — Device Trust. Primary volume: DS-021.

## 5. Supporting Requirement Families

- DS-SCA (DS-008) — existing security-control catalog this volume extends for the multi-device/multi-tenant surface.
- DS-SEC (DS-002) — existing security/privacy product requirements (e.g. no client-embedded secrets) this volume's IP-protection controls build on.
- DS-MUA (DS-020) — multi-user/multi-account surface this volume's device-trust model must secure.

## 6. Dependencies

- DS-008 (Security Architecture) — sole existing security authority; this volume is additive, not a parallel authority.
- DS-015 (Editions) — build-exclusion mechanism this volume's IP-protection controls (code signing, attestation) help enforce.
- DS-020 (Multi-User) — delegated-access authentication this volume secures.

## 7. Major Sections (Planned for Full Draft)

1. Device Trust Model (Registration, Verification, Revocation)
2. Multi-Factor Authentication for Customer Accounts
3. Secret Management for Distributed Clients
4. Code Signing and Build Attestation
5. Founder Asset Extraction-Resistance
6. Security Incident Response for the Expanded Attack Surface

## 8. Cross-Volume References

- DS-008 (Security Architecture), DS-002 (DS-SEC), DS-015 (Editions), DS-018 (Sage Deployment — Founder Local Sage as the highest-value IP-protection target), DS-020 (Multi-User, Multi-Account), DS-023 (Reliability, Operations, Data Governance, and Recovery).

## 9. Acceptance Criteria (Placeholders)

- [ ] No secret is ever embedded in a customer client (extends existing DS-SEC-001 verification to every new distributed-client surface).
- [ ] No customer build can include a Founder-only asset (verified mechanically, cross-referenced with DS-015).
- [ ] Every trusted device can be independently revoked without affecting other devices on the same account.

## 10. Traceability (Placeholders)

- [ ] DS-DVT-001 … (allocated in `docs/features/FEATURE_GOVERNANCE.md`; full requirement text deferred).

## 11. Release-Stage Responsibilities

| Stage | Responsibility |
|---|---|
| Stage 4 (Customer Cloud Beta) | Device trust and MFA enter beta for customer accounts. |
| Stage 5 (Initial Commercial Release) | Device trust, MFA, and IP-protection controls are release-required and independently verifiable. |

## 12. Open Decisions

- Exact MFA mechanism(s) offered (TOTP, hardware key, SMS as a fallback only) — deferred to full draft, with SMS-as-primary explicitly disfavored given known weaknesses.
- Attestation mechanism specifics (platform-native attestation vs. custom) — deferred.

## 13. Known Risks

- Founder-private assets (Local Sage, proprietary research methodology) are the single highest-value target in the whole system; this volume's full draft must treat extraction-resistance as a Critical-severity design requirement, not an afterthought.
- Device-trust/MFA rollout friction could depress activation if not designed carefully — a UX concern shared with DS-022.

## 14. Founder Sage Developer Mode (`FEAT-0268`) — Sandboxing and Security Boundary, Added 2026-07-26

**Status:** structural skeleton only, not a full requirement draft. DS-021 supports the sandboxing/secrets/repository-security boundary for this Founder-only capability; DS-018 is its primary owner (see DS-018 §14).

- **Repository allowlist:** Developer Mode may only read/write within an explicit, configured repository allowlist; no access to unrelated filesystem paths by default.
- **Sandboxed or policy-controlled command execution:** every command Developer Mode runs is either sandboxed or checked against an explicit **command allowlist and denylist**; nothing outside the allowlist executes without an explicit, separate Founder approval step.
- **Path containment:** all file operations are contained to the allowlisted repository tree, mirroring the existing repository-safe path-resolution pattern this Codex's own publication tooling already uses (`scripts/publication/_repo.py:resolve_repo_path`).
- **Secrets redaction and credential isolation:** Developer Mode never reads, logs, or reproduces a real secret/credential value; secrets are redacted at the boundary and isolated from any model context.
- **Protected-branch safeguards:** no force-push, no history rewrite, and no deletion of a protected branch, under any configuration.
- **No unauthorized security/privacy boundary changes:** Developer Mode cannot alter a security or privacy control (this volume, DS-008, or DS-015's edition boundary) without explicit, separate Founder approval and independent validation.
- **No production credential modification** and **no secret disclosure**, under any configuration or prompt.
- **No customer-build inclusion:** Developer Mode's tooling, prompts, and any Founder-private model asset it uses are excluded from every customer build (see DS-015 §12a).
- Founder-private model, prompt, tool, and repository assets that Developer Mode touches are protected under this volume's IP-protection controls (§7.5, Founder Asset Extraction-Resistance) on the same footing as Founder Local Sage.
