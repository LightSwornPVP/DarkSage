# Publication Evidence Requirements

This document defines the evidence required to promote DarkSage volumes through publication states.

## Evidence Requirements for Released Volumes

A volume marked Released must include:

- approved Markdown path;
- final DOCX path;
- final PDF path;
- checksum verification;
- release manifest entry;
- independent approval evidence.

## Legacy Core Volume Exception

DS-001 through DS-014 were released before this register existed and are exempt from the `approved_by`/`approved_date` fields; see `PUBLICATION_PROMOTION_RULES.md`. All other Released-volume evidence requirements still apply.

## Evidence Requirements for Draft/Skeleton Volumes

Draft and Skeleton volumes may omit final DOCX/PDF artifacts, but they must not claim Released.

## Path Safety

All file paths in publication registers must resolve safely inside the repository and may not contain relative traversal sequences such as `..`.
