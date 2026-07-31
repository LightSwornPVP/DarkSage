# ADR-003 — Deterministic Financial Calculations

## Document Control

| Field | Value |
|---|---|
| Document ID | ADR-003 |
| Title | Deterministic Financial Calculations |
| Version | 1.1.0 |
| Status | Approved |
| Owner | TheSinnerMan |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-23 |
| Last Updated | 2026-07-24 |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Context

DS-001 §12 states "Deterministic Financial Truth: material financial calculations shall come from deterministic implementations" as one of DarkSage's foundational Product Experience Principles, and DS-001 §15 further distinguishes deterministic results, observed data, inferred context, and advisory interpretation, warning against explainability becoming "a performance of certainty." DS-001 explicitly states DarkSage is not "a platform that uses generative AI as the authoritative engine for deterministic financial calculations." This ADR formalizes that boundary so risk math, backtests, portfolio calculations, indicators, and execution sizing remain reproducible and testable regardless of which AI capabilities are later added.

## Decision

Material financial calculations shall use deterministic implementations rather than generative model output.

## Consequences

### Positive

- Enables reproducibility, auditability, and regression testing of every material financial result (DS-009 deterministic-calculation test requirements), since deterministic implementations produce the same output for the same input by construction.
- Prevents AI hallucination or model drift from ever becoming financial truth — Sage may reason about and explain deterministic results (ADR-002), but never substitutes generative output for them.
- Establishes a clear engine boundary that DS-004's architecture (deterministic calculation engine, AI-provider abstraction) and DS-003's Sage boundary both build on without re-deriving it independently.

### Negative

- Constrains where generative AI may be used even for exploratory or novel calculation approaches: any such approach must be reduced to a deterministic, testable implementation before it can be treated as authoritative, which can slow the path from AI-assisted research (e.g., DS-014's model-research cluster) into committed product authority.
- Requires ongoing engineering discipline to keep deterministic and AI-assisted code paths from becoming tightly coupled (DS-004's anti-coupling requirement), since any coupling would risk silently blurring the boundary this ADR establishes.

## Alternatives Considered

No alternative computation model (e.g., AI-assisted or AI-verified financial calculation as an authoritative source) is recorded in this decision's approved history. DS-001 explicitly rules out generative AI as "the authoritative engine for deterministic financial calculations," leaving no partial-authority variant for this repair to record as a considered-and-rejected alternative.

## Related Requirements

- DS-001 — Executive Vision & Product Foundation, §12 (Deterministic Financial Truth), §15 (Explainability Standard)
- DS-003 — Sage AI Bible: Core Rule and DS-SGE-001 through DS-SGE-007 (deterministic/advisory boundary)
- DS-004 — Technical Architecture: deterministic calculation engine and AI-provider abstraction boundary; anti-coupling requirement (`ARCHITECTURE.md` §30)
- DS-009 — Testing and QA: deterministic financial calculation test requirements

## Decision History

| Version | Date | Status | Owner | Summary |
|---|---|---|---|---|
| 1.0.0 | 2026-07-23 | Approved | TheSinnerMan | Approved initial controlled baseline; metadata normalization of the existing decision. Decision content unchanged. |
| 1.1.0 | 2026-07-24 | Approved | TheSinnerMan | Consolidated cleanup pass: populated previously template-minimal Context, Consequences, Alternatives Considered, and Related Requirements sections from already-approved DS-001/DS-003/DS-004/DS-009 content. Decision content unchanged; approved status and authority preserved. |
