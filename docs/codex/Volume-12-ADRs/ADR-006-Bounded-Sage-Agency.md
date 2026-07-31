# ADR-006 — Bounded Sage Agency and Tool Orchestration

| Field | Value |
|---|---|
| Document ID | ADR-006 |
| Version | 1.0.0 |
| Status | Approved |
| Owner | TheSinnerMan |
| Date | 2026-07-25 |

## Decision
Sage may perform visible, permission-scoped multi-step work through registered tools, including research, deterministic analysis, strategy drafting, thesis monitoring, and review coaching. Sage cannot grant itself tools, alter policy, write authoritative deterministic figures, bypass Guardian, or directly approve/execute broker actions.

## Consequences
Tool calls require validation, audit, cancellation where practical, and prompt-injection defenses. Agent usefulness is preserved without merging intelligence and execution authority.
