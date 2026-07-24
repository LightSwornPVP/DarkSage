# The DarkSage Codex

The Codex is the authoritative engineering documentation system for DarkSage.

## Source-of-Truth Rule

- Markdown files are authoritative for engineering work.
- Word documents are polished human-facing editions.
- When the two differ, update Markdown first and regenerate Word.

## Status Workflow

`Draft → Under Review → Approved → Superseded/Deprecated`

- **Superseded:** replaced by a newer authoritative document or version.
- **Deprecated:** retained for historical or reference purposes but no longer recommended or current.

## Versioning

Codex documents use semantic versioning:

- Major: structural or policy-breaking change
- Minor: approved expansion
- Patch: correction or clarification

## Core Policy

Major features must be documented before implementation.
