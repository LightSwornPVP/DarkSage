# DarkSage Diagram Standard
**Version:** 1.0.0

## Supported Diagram Classes
- System context
- Component
- Data flow
- Sequence
- State machine
- Entity relationship
- Trust boundary/security
- AI pipeline
- Risk flow
- Deployment

## Rules
Every controlled diagram must have an ID, title, version/source reference, legend when symbols are non-obvious, and explicit system/trust boundaries where relevant.

## Source
Prefer text-source diagrams (for example Mermaid) when practical so diagrams remain diffable in Git. Exported images belong in `docs/assets/diagrams/`.

## Semantics
Arrows must have direction and labels when the meaning is not self-evident. Do not mix logical architecture and deployment topology in one diagram unless clearly separated.
