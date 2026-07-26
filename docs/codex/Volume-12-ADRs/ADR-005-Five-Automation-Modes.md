# ADR-005 — Five Automation Modes and Policy-Based User Authority

| Field | Value |
|---|---|
| Document ID | ADR-005 |
| Version | 1.0.0 |
| Status | Approved |
| Owner | TheSinnerMan |
| Date | 2026-07-25 |

## Decision
DarkSage uses five explicit states: Advisory Only, Confirmation Required, Full-Auto Paper, Restricted Full-Auto Live, and Paused/Emergency Stopped. User authority may be expressed through per-action confirmation or prior explicit activation of a bounded automation policy. Sage never directly executes orders. Full-Auto Paper may run unattended. Restricted Full-Auto Live remains future-gated by dedicated controls and independent approval.

## Consequences
Every action path must be tested against the mode matrix. Policy scope, limits, expiry, and emergency controls are visible and auditable. Failure or ambiguity is fail-closed.
