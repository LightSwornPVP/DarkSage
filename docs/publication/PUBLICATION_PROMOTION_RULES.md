# Publication Promotion Rules

This document defines valid publication state transitions for DarkSage volumes.

## Allowed States

- Released
- Approved for Publication
- Publication In Progress
- Draft
- Skeleton
- Blocked
- Deprecated
- Superseded

## Valid Transitions

- Skeleton → Draft
- Draft → Approved for Publication
- Approved for Publication → Publication In Progress
- Publication In Progress → Released
- Released → Deprecated
- Deprecated → Superseded

## Promotion Requirements

A volume must not be marked Released until:

- normative Markdown is complete;
- all controlled IDs validate;
- acceptance criteria are complete;
- traceability is complete;
- independent review is complete;
- DOCX is generated;
- PDF is generated;
- metadata is synchronized;
- semantic extraction checks pass;
- checksum and byte counts are recorded;
- release manifest is synchronized;
- publication validator passes;
- final approval is recorded.

## Expansion Volumes

DS-015 through DS-023 are expansion draft volumes. They may be marked Skeleton or Draft, but they may not be marked Released.

## Legacy Core Volumes

DS-001 through DS-014 (the Core Codex) were released prior to the creation of this publication state register and are locked as-is; their register rows are not modified by this or later publication passes. Their approval history predates `approved_by`/`approved_date` tracking, so these two fields are not required for Released rows in that range. All other release requirements (Markdown, DOCX, PDF, checksum, release manifest entry) still apply.

## Blocked and Superseded States

- Blocked indicates a volume cannot currently progress due to unresolved dependencies, missing evidence, or policy conflict.
- Superseded indicates a volume has been replaced by a later approved volume or a different controlled publication path.
