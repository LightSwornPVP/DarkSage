# ADR-002 — Sage Cannot Bypass the Risk Engine

## Document Control

| Field | Value |
|---|---|
| Document ID | ADR-002 |
| Title | Sage Cannot Bypass the Risk Engine |
| Version | 1.1.0 |
| Status | Approved |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Context

DS-001 §12's foundational principle "Sage Advises; the User Decides" and §13 (Risk Philosophy) establish that Sage — DarkSage's AI-assistance layer — must never become an unquestionable authority or gain execution authority over trading decisions. DS-003 (Sage AI Bible) instantiates this boundary as a Core Rule: Sage may never directly submit an order or access/call the Execution Engine or Broker Adapter under any circumstance, including after user confirmation. This ADR formalizes that boundary as an architectural decision so no future feature, prompt pattern, or integration can erode it without a new ADR.

## Decision

Sage may advise and calculate. Sage cannot bypass or silently override the Risk Engine.

## Consequences

### Positive

- Preserves a single deterministic, auditable risk and execution-authorization boundary (the canonical `TradeValidationPipeline`) regardless of which advisory system produced a trade idea.
- Prevents AI/LLM output from becoming an implicit or emergent source of trading authority, supporting the fail-closed safety posture required elsewhere in the Codex (DS-003 DS-SGE-005/020; DS-002 DS-PRD-011).
- Keeps Sage's value proposition scoped to what generative AI is suited for — reasoning, synthesis, explanation, personalization — rather than positioning it as a deterministic financial authority (ADR-003).

### Negative

- Sage cannot autonomously act on its own conclusions even when confident; every Sage-originated trade idea must pass through the full Risk Engine and `TradeValidationPipeline` regardless of Sage's own assessment. This is an intentional constraint on convenience, not an oversight.
- Adversarial or manipulative attempts to talk Sage into bypassing this boundary (prompt injection, role-play) must be actively resisted (DS-003 DS-SGE-019), adding an ongoing security-hardening obligation rather than a one-time architectural fix.

## Alternatives Considered

No alternative authority model (e.g., allowing Sage conditional or supervised execution authority) is recorded in this decision's approved history. The Core Rule in DS-003 states this boundary applies "under any circumstance, including after user confirmation," leaving no partial-authority variant for this repair to record as a considered-and-rejected alternative.

## Related Requirements

- DS-001 — Executive Vision & Product Foundation, §12 (Sage Advises; the User Decides), §13 (Risk Philosophy)
- DS-003 — Sage AI Bible: Core Rule (execution-boundary), DS-SGE-001 through DS-SGE-007, DS-SGE-019 (adversarial resistance), DS-SGE-020 (AI-output validation)
- DS-002 — Software Requirements Specification: DS-PRD-011 (AI Output Validation)

## Decision History

| Version | Date | Status | Owner | Summary |
|---|---|---|---|---|
| 1.0.0 | 2026-07-23 | Approved | TheSinnerMan | Approved initial controlled baseline; metadata normalization of the existing decision. Decision content unchanged. |
| 1.1.0 | 2026-07-24 | Approved | TheSinnerMan | Consolidated cleanup pass: populated previously template-minimal Context, Consequences, Alternatives Considered, and Related Requirements sections from already-approved DS-001/DS-003/DS-002 content. Decision content unchanged; approved status and authority preserved. |
