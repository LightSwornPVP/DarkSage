# ADR-007 — External Notifications Are Non-Authoritative by Default

| Field | Value |
|---|---|
| Document ID | ADR-007 |
| Version | 1.0.0 |
| Status | Approved |
| Owner | TheSinnerMan |
| Date | 2026-07-25 |

## Decision
Discord, email, OS notifications, mobile push, and future external channels are notification-only by default. They may deliver alerts, reports, and authoritative-record references, but cannot approve, place, modify, cancel, or otherwise control trades without a separate future ADR, threat model, strong authentication, and explicit authority design.

## Consequences
Notification adapters remain isolated from execution operations. Secrets are protected, content is minimized, delivery is idempotent, and the in-product event record remains authoritative.
