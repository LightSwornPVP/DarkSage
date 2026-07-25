# DSF-003 — DarkSage Visual Design System

## Document Control

| Field | Value |
|---|---|
| Document ID | DSF-003 |
| Title | DarkSage Visual Design System |
| Version | 0.2.0 |
| Status | Draft |
| Owner | Keeper (delegated authority) |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |
| Source Baseline Commit | e2f73a7ade28ce97caad1eb2e06d43ef0ac0aed8 (docs: add DarkSage publication architecture and PRS) — verified against `git rev-parse HEAD` in this pass |
| Controlling Sources | [DSF-001](DARKSAGE_PUBLICATION_ARCHITECTURE.md) §A, §C–§I (this document elaborates, and is subordinate to, DSF-001 for all palette, typography-role, page-system, component, diagram-inventory, workflow, and quality-gate decisions already made there); `docs/standards/BRAND_GUIDE.md`, `DIAGRAM_STANDARD.md`, `DOCUMENTATION_STANDARD.md`, `STYLE_GUIDE.md` |
| Authority Boundary | Publication-only, per `docs/standards/NAMING_AND_ID_STANDARD.md`'s `DSF-NNN` namespace. This document adds production-level detail (exact page/grid dimensions, spacing scale, extended callout catalog, requirement-card field spec, accessibility checklist, document-family variants) that DSF-001 scoped but did not itself state numerically. It creates no product-requirement authority and originates no Codex meaning. Where this document and DSF-001 differ, DSF-001 governs and this document is a defect to be corrected — it never supersedes DSF-001. |
| Publication Relationship | Subordinate to [DSF-001](DARKSAGE_PUBLICATION_ARCHITECTURE.md) per DSF-001 §A's three-tier publication authority hierarchy; used by the templates in `docs/publication/templates/`, the diagram assets in `docs/publication/diagrams/`, and the Executive Product Plan draft. |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

## Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| 0.1.0 | 2026-07-25 | Keeper (delegated authority) | First controlled draft. Elaborates DSF-001 §C–§F with production-level detail not previously stated numerically: exact page sizes/margins/grid/spacing scale, print-safe and grayscale color behavior, the full reusable-callout catalog (adding the callouts DSF-001 did not yet define: Advisory AI, Fail Closed, Example, Contradiction (standalone), Acceptance Criteria (standalone visual spec), Edge Case (standalone visual spec), Testing Expectation (standalone visual spec), Pending Traceability, Founder Decision Required), the requirement-card field-by-field spec, an accessibility checklist, and document-family variants for the three flagship families. Introduces no new palette value, page type, or diagram — all colors and page/component names are taken from DSF-001 verbatim. |
| 0.2.0 | 2026-07-25 | Keeper (delegated authority) | Independent-audit repair. **HIGH6 (functional-color accessibility):** §2.2/§2.3 recalculated — the prior draft's blanket claim that every functional color reached ≥4.5:1 against Ivory White was false for two of four colors (Signal Green `#2E8B57` measured 3.79:1, Warning Amber `#C58A1B` measured 2.67:1, both below the 4.5:1 normal-text minimum; Warning Amber also below the 3:1 large-text/graphical minimum). Replaced both with darker, hue-preserving, recalculated-compliant values for text/icon/semantically-meaningful-graphical use: Signal Green (Text/Icon) `#1E6E43` (5.57:1) and Warning Amber (Text/Icon) `#8A6013` (4.98:1). Risk Red (`#A33A3A`, 5.82:1) and Info Blue (`#3B6EA5`, 4.74:1) were already compliant and are unchanged. Added an explicit text-use rule, icon/graphical-use rule, and fill/decorative-use exception; documented that BRAND_GUIDE.md's own general documentation palette is unchanged and out of this pass's scope. **Non-blocking (callout count):** corrected §7's "sixteen reusable callouts" claim to the actual count of seventeen (eight in §7.1 + nine in §7.2) rather than dropping a genuinely distinct, non-duplicated callout to force the old number. **Non-blocking (baseline accuracy):** Source Baseline Commit corrected to the full hash, verified against `git rev-parse HEAD`; no stale `ed27a71` reference was found anywhere in this document (none existed to correct). No palette value used elsewhere in the document, page-type name, or component name outside §2.2/§2.3/§7 was changed. |

## 1. Purpose and Relationship to DSF-001

DSF-001 §C–§I establishes the DarkSage visual identity, typography roles, page systems, component system, diagram inventory, generation workflow, and quality gates at the architecture level. This document (DSF-003) operationalizes that architecture into production-ready specifications a template author, diagram author, or future generation-tooling author can implement directly, without re-deciding anything DSF-001 already settled.

**Non-goal:** DSF-003 does not redefine the palette, does not rename a page type, does not reclassify a diagram, and does not weaken any DSF-001 §A authority rule. Every hex value, page-type name, and component name in this document is copied verbatim from DSF-001; only numeric/production detail is added.

## 2. Color System

### 2.1 Primary Palette (verbatim from DSF-001 §C.1)

| Name | Hex | Role |
|---|---|---|
| Obsidian Black | `#0B0B0D` | Covers, divider pages, dark UI chrome |
| Charcoal Gray | `#17181C` | Secondary dark surface, cover sub-panels |
| Steel Gray | `#2A2D33` | Structural lines, table borders on dark surfaces |
| Soft Gray | `#A7ABB3` | Secondary/muted text, captions, metadata rows |
| Ivory White | `#F4F2EC` | Body page background, light-mode primary surface |
| Sage Gold | `#C8A45D` | Restrained hierarchy accent: section rules, requirement IDs, selected-state emphasis |
| Highlight Gold | `#E0BE72` | Premium emphasis only — cover titles, key-decision callouts, volume-divider numerals |

### 2.2 Functional Colors

Distinct from the brand palette and never substituted for it. Always paired with a text label or icon (never color alone, DSF-001 §C.2 rule 3).

| Function | Color | Hex | Use |
|---|---|---|---|
| Confirmed / positive | Signal Green (Text/Icon) | `#1E6E43` | Validated status, pass state, confirmed evidence — text, icon glyphs, and any graphical element carrying semantic meaning |
| Rejection / risk / danger | Risk Red | `#A33A3A` | Safety Boundary callouts, risk disclosures, blocking findings |
| Warning / uncertainty | Warning Amber (Text/Icon) | `#8A6013` | Open Question, Contradiction, caution states — text, icon glyphs, and any graphical element carrying semantic meaning |
| Informational / system | Info Blue | `#3B6EA5` | System-state notes, non-risk informational asides |

Risk Red and Info Blue are taken from `docs/standards/BRAND_GUIDE.md`'s existing documentation palette (Signal Green, Warning Amber, Risk Red) so the publication system and the repository's general documentation guide stay consistent for those two colors; Info Blue is added here since BRAND_GUIDE.md does not define an informational color and DSF-001 §F references a fourth, non-risk state ("informational/system state") without assigning it a value. **Signal Green and Warning Amber are recalculated for this document only** (§2.3 HIGH6 repair) — `#1E6E43`/`#8A6013` replace BRAND_GUIDE.md's `#2E8B57`/`#C58A1B` specifically for any text, icon, or semantically-meaningful graphical use in a DSF-NNN publication artifact, because the original BRAND_GUIDE.md values fail the WCAG 2.2 AA contrast this document itself requires against Ivory White (§2.3). BRAND_GUIDE.md's own general documentation palette is unchanged and out of this pass's scope; this is a publication-tier divergence for accessibility, not a BRAND_GUIDE.md correction.

### 2.3 Contrast Requirements

- Body text (near-Obsidian, `#0B0B0D`-family) on Ivory White (`#F4F2EC`) background: contrast ratio ≥ 7:1, exceeding WCAG 2.2 AA's 4.5:1 minimum for normal text (targets AAA where achievable without narrowing the palette).
- Sage Gold (`#C8A45D`) is never used for body-text-sized type directly on Ivory White; its measured contrast against `#F4F2EC` falls below 3:1 and is reserved for rules, chips with sufficient chip-fill contrast, and large/bold display text only (WCAG 2.2 AA large-text threshold, ≥3:1, 18pt+/14pt+bold).
- Highlight Gold (`#E0BE72`) on Obsidian Black (`#0B0B0D`) or Charcoal Gray (`#17181C`) cover backgrounds: contrast ratio ≥ 7:1, safe for cover titles at any size.
- **Functional colors (§2.2), recalculated (HIGH6 repair) — verified contrast against Ivory White (`#F4F2EC`), WCAG 2.2 relative-luminance formula, computed by `scripts/publication/validate_publication.py`'s contrast check:**

  | Color | Hex | Contrast vs. Ivory White | Meets 4.5:1 (normal text) | Meets 3:1 (large text/graphical) |
  |---|---|---|---|---|
  | Signal Green (Text/Icon) | `#1E6E43` | 5.57:1 | Yes | Yes |
  | Risk Red | `#A33A3A` | 5.82:1 | Yes | Yes |
  | Warning Amber (Text/Icon) | `#8A6013` | 4.98:1 | Yes | Yes |
  | Info Blue | `#3B6EA5` | 4.74:1 | Yes | Yes |

  The prior draft's blanket claim ("each verified ≥ 4.5:1") was false for two of the four colors as originally specified: the BRAND_GUIDE.md-sourced Signal Green (`#2E8B57`) measured 3.79:1 and Warning Amber (`#C58A1B`) measured 2.67:1 against Ivory White — both below the 4.5:1 normal-text minimum, and Warning Amber also below the 3:1 large-text/graphical minimum. Risk Red (5.82:1) and Info Blue (4.74:1) already passed and are unchanged.
- **Text-use rule:** any functional color used as text (a label, a numeral, an inline status word) or as an icon glyph carrying semantic meaning uses the Text/Icon hex above, never the original BRAND_GUIDE.md Signal Green/Warning Amber values.
- **Icon/graphical-use rule:** any non-text graphical element whose fill or stroke itself carries semantic meaning (a status dot, a severity bar, a chart segment) also uses the Text/Icon hex above, since DSF-001 §C.2 rule 3 requires every color-coded element to carry meaning accessibly, not only text.
- **Fill/decorative-use exception:** a functional color used purely as a callout left-rule accent or panel background fill (not itself the carrier of meaning — the callout's text label carries the meaning, per §2.2) is not subject to the 4.5:1/3:1 thresholds for that fill itself; the callout's own label text still follows the near-Obsidian-on-Ivory rule, unchanged from the prior draft.
- **Grayscale/fallback meaning:** unchanged from §2.5 — every functional-color callout remains distinguishable via text label and left-rule line weight, not fill or hue alone.
- **Color is never the sole carrier of meaning** — restated from §2.2/DSF-001 §C.2 rule 3; the hex changes in this repair affect measured contrast only, not this existing rule.

### 2.4 Print-Safe Alternatives

- All seven primary-palette and four functional colors are specified as CMYK-safe equivalents for print generation, computed at generation time from the sRGB hex values above rather than hand-tuned per print run, avoiding a second, drift-prone color source.
- Highlight Gold is never used as a small-text color in print; print layouts substitute Sage Gold for any print run where the target printer's gamut cannot reproduce Highlight Gold's saturation reliably (a generation-tool-level fallback, not a change to the digital palette).

### 2.5 Grayscale Behavior

- Every functional-color callout (§2.2) remains distinguishable in grayscale print/photocopy via its text label and left-rule line weight, not fill alone: Risk Red → heaviest rule weight + "SAFETY BOUNDARY"/"RISK" label; Warning Amber → medium rule weight + "OPEN QUESTION"/"CONTRADICTION" label; Signal Green → light rule weight + explicit "CONFIRMED" label; Info Blue → dotted rule + explicit label.
- Status/classification badges (DSF-001 §F) already use shape distinction (filled pill / outline pill / dashed pill) in addition to color, per DSF-001's own rule — this satisfies grayscale legibility without further change.

### 2.6 Dark-Cover vs. Light-Body Rule (restated from DSF-001 §C.2 rules 4–5)

Cover and divider pages (DSF-001 §E.1, §E.5) may use Obsidian Black/Charcoal Gray freely. Every other page type in §E.2–§E.13 uses an Ivory White (or warm-light) background with near-Obsidian text. No exception.

## 3. Typography

### 3.1 Role Assignments (per DSF-001 §D, restated with production point sizes)

| Role | Preferred Candidate | Portable Fallback Stack | Target Size |
|---|---|---|---|
| Cover / display | Aptos Display, Bold/Semibold | Source Serif 4 Bold → Liberation Serif Bold → DejaVu Serif Bold | 36–54pt (cover title) |
| Section heading (H1–H3) | Aptos Display, Semibold | Source Sans 3 Semibold → Liberation Sans Bold → DejaVu Sans Bold → Noto Sans Bold | H1 20–24pt / H2 16–18pt / H3 13–14pt |
| Body text | Aptos, Regular | Source Sans 3 Regular → Liberation Sans Regular → DejaVu Sans Regular → Noto Sans Regular | 10–11pt |
| Captions / metadata | Aptos, Regular, Soft Gray | Source Sans 3 Regular → Liberation Sans Regular → DejaVu Sans Regular | 8–9pt |
| Tables | Aptos, Regular (header Semibold) | Source Sans 3 → Liberation Sans → DejaVu Sans → Noto Sans | 9–10pt (one step below body) |
| Requirement IDs (inline) | Consolas | JetBrains Mono → Liberation Mono → DejaVu Sans Mono | Match surrounding body size |
| Code / config blocks | Consolas | JetBrains Mono → Liberation Mono → DejaVu Sans Mono | 9–10pt |

Font rules (restated from DSF-001 §D and the task's font-availability constraint): Aptos, Aptos Display, and Consolas are environment-dependent candidates only — never assumed present, never committed as binaries, never distributed from this repository. The portable fallback stack listed above is the actually-verifiable option set for a Linux/CI generation environment; a generation run **shall** detect actual font availability at run time (§ Generation Tooling, `scripts/publication/`) and record whichever font in the stack it actually used in the generated artifact's metadata (never silently substitute without recording it).

### 3.2 Line Length, Weights, Hierarchy

Restated verbatim from DSF-001 §D.3/§D.7 for a single-source production reference: target 70–90 characters per body line; no more than two weights (Regular, Semibold/Bold) per typeface family per document; exactly one H1 per document; heading levels never skip.

## 4. Layout Grid

### 4.1 Page Sizes

| Target | Size | Use |
|---|---|---|
| Letter | 8.5in × 11in (215.9mm × 279.4mm) | Primary target — US-audience default for all three flagship families |
| A4 | 210mm × 297mm | Secondary target where an international print run is requested; content reflows, never crops, between Letter and A4 |

### 4.2 Margins

| Page Type | Top | Bottom | Inside/Left | Outside/Right |
|---|---|---|---|---|
| Cover (DSF-001 §E.1) | 1.25in | 1.25in | 1in | 1in |
| Divider (DSF-001 §E.5) | 1.5in | 1.5in | 1in | 1in |
| Normal content (DSF-001 §E.7) | 1in | 1in | 1.1in (allows binding/gutter) | 0.9in |
| Chapter opener (DSF-001 §E.6) | 1.5–2in (per DSF-001, ~1.5–2x normal top margin) | 1in | 1.1in | 0.9in |

### 4.3 Columns and Baseline Rhythm

- Single-column body text for all normal content, requirement card, ADR, and appendix pages (DSF-001 §E.7–§E.11); two-column permitted only for the Glossary/Index page (DSF-001 §E.12).
- Baseline rhythm: 12pt leading at 10pt body size (1.2x line-height ratio), consistent across all body pages so paragraph rhythm does not visibly shift between sections.

### 4.4 Paragraph and Heading Spacing

- Paragraph spacing: 6pt space-after, no first-line indent (block-paragraph style, consistent with the Codex Markdown source's own block style).
- Heading spacing: H1 24pt space-before / 12pt space-after; H2 18pt space-before / 8pt space-after; H3 12pt space-before / 6pt space-after — spacing scales down with heading level so hierarchy reads by whitespace as well as size.

### 4.5 Line-Length Limits

70-90 characters per line for body text (§3.2); dense reference tables (Codex Complete Edition traceability/glossary pages) may exceed this within their own bounded table width, never in flowing prose.

### 4.6 Page-Break Rules

- A heading never appears as the last line on a page with no following content line before the next page break (orphan heading, prohibited per DSF-001 §I.5).
- A requirement card's ID/Title header and classification badge never separate from at least its first content line across a page break (DSF-001 §E.8).
- A diagram never spans a page break (DSF-001 §E.10); it is presented as a fold-out/landscape page or an explicitly labeled multi-part figure instead.
- A table's header row repeats on the following page if the table itself spans a page break; a table row is never split mid-row across a page break.

### 4.7 Widow/Orphan Prevention

Minimum two lines of a paragraph must appear together at the top or bottom of a page (standard widow/orphan control) — a single stranded line at a page top or bottom is treated as a layout defect for generation-tool QA (DSF-001 §I).

### 4.8 Table Overflow Behavior

A table wider than the body text column: first attempt is font-size step-down within Table Typography's allowed range (DSF-001 §D.5, 9-10pt); if still too wide, the table is presented in landscape orientation on its own page; a table is never truncated, horizontally clipped, or silently reduced to fewer columns than its Markdown source.

## 5. Document Templates

Template source files live in `docs/publication/templates/` (Deliverable 2 of this batch) and implement, one file per type, exactly the thirteen page types DSF-001 §E.1–E.13 already named: Cover Page, Document-Control Page, Legal/Disclaimer Page, Table of Contents, Volume Divider, Chapter Opener, Normal Content Page, Requirement Page/Card, ADR Page, Diagram Page, Appendix Page, Glossary/Index Page, Revision-History Page. This document does not restate each template's Markdown structure — see the template files themselves and `docs/publication/templates/README.md` for the authoritative reusable source.

## 6. Headers and Footers

Restated and made exact from DSF-001 §E.2/§E.7:

**Header (left):** DarkSage name + document short title.
**Header (right):** Document ID (e.g., `DSF-002`) in monospace (§3.1).
**Footer (left/outer):** Page number.
**Footer (right/opposite):** Classification (e.g., "Internal").
**Footer (center, small, Soft Gray):** Version + Status (e.g., "v0.2.0 - Draft") and, on any page reproducing generated-artifact content, a generated-artifact marker reading "Generated from `<SourceDocumentID>` v`<version>` - baseline `<commit>`" (DSF-001 §A.2.6).
**Cover/divider pages:** No running header/footer (DSF-001 §E.1/§E.5) - metadata appears once in the cover's own content block instead.

## 7. Reusable Callouts

The following table is the complete catalog of seventeen reusable callouts (non-blocking count repair: the prior draft's revision history and this paragraph both said "sixteen" while the two subsections below actually listed eight plus nine — seventeen — entries; the miscount is corrected here rather than dropping a genuinely distinct, non-duplicated callout). The first eight are defined in DSF-001 §F and are restated here verbatim for a single production reference; the second nine are new in this document, filling the gap between DSF-001's initial component list and the task's callout requirement. No callout defined here contradicts, renames, or duplicates a DSF-001 callout or another entry in this table.

### 7.1 Previously Defined (DSF-001 §F, restated)

| Callout | Visual Treatment | Use |
|---|---|---|
| Product Principle | Ivory panel, Sage Gold left-rule, small-caps label "PRINCIPLE" | DS-001 Constitution items, foundational principles |
| Safety Boundary | Ivory panel, Risk-Red left-rule, red small-caps label "SAFETY BOUNDARY" + icon | ADR-002-class content, `TradeValidationPipeline` integrity statements, fail-closed rules |
| Deterministic Authority | Ivory panel, Steel-Gray left-rule, label "DETERMINISTIC" | ADR-003-class content, deterministic-calculation statements |
| Research / Non-Committed | Ivory panel, dashed Soft-Gray border, label "NON-COMMITTED — RESEARCH REFERENCE" | DS-014 idea entries, third-party model/reference citations under DS-IDG-004 |
| Open Question | Ivory panel, amber left-rule, label "OPEN QUESTION" | Appendix entries genuinely unresolved in the source |
| Risk / Warning | Ivory panel, Risk-Red left-rule + warning icon, label "RISK" | Material risk disclosures |
| Note | Ivory panel, Soft-Gray left-rule, label "NOTE" | Non-normative clarifying remarks |
| Evidence / Contradiction panel | Two-column panel (Evidence / Conflict), amber header if a genuine conflict is disclosed | Sage evidence-conflict disclosure (DS-SGE-009), audit-finding contradiction records |

### 7.2 New in DSF-003

| Callout | Visual Treatment | Use |
|---|---|---|
| Advisory AI | Ivory panel, Info-Blue left-rule, label "ADVISORY — SAGE" | Any Sage-originated explanation, synthesis, or suggestion, to visually distinguish advisory AI output from deterministic system output at a glance, per ADR-002/DS-PRD-006 |
| Fail Closed | Ivory panel, Risk-Red left-rule (heavier weight than Safety Boundary), label "FAIL CLOSED" + lock icon | Statements describing a system's behavior under ambiguity/error/timeout defaulting to the safe/blocked state rather than proceeding |
| Example | Bordered panel, dashed Steel-Gray border, header "ILLUSTRATIVE EXAMPLE — NOT LIVE DATA" (matches DSF-001's "Example trade assessment" treatment, generalized to any illustrative example, not only trade assessments) | Any worked example, sample payload, or illustrative walkthrough |
| Contradiction (standalone) | Ivory panel, amber left-rule, label "CONTRADICTION" | A single disclosed contradiction cited outside the two-column Evidence/Contradiction panel format (e.g., inline in prose) |
| Acceptance Criteria (standalone) | Bulleted checklist glyph (a hollow box, not a colored checkmark implying completion), label "ACCEPTANCE CRITERIA" | Requirement-card acceptance-criteria blocks presented outside a full card (e.g., a compact requirement summary) |
| Edge Case (standalone) | Indented bullet, smaller type than Acceptance Criteria, label "EDGE CASE" | Requirement-card edge-case blocks presented outside a full card |
| Testing Expectation (standalone) | Monospace label "TESTING:" prefix + description, Steel-Gray left-rule | Requirement-card testing-direction blocks presented outside a full card |
| Pending Traceability | Ivory panel, dotted Soft-Gray border, label "TRACEABILITY: PENDING" | Any traceability-matrix cell/reference in a Pending state (DSF-002 §21), so a reader recognizes "Pending" as the honestly-recorded current state rather than a missing/broken reference |
| Founder Decision Required | Ivory panel, Highlight-Gold left-rule (the one body-page use of Highlight Gold, reserved for genuine escalation), label "FOUNDER DECISION REQUIRED" | Any item requiring Founder/root-governance decision rather than routine editorial judgment — reserved for genuine escalations only, never used decoratively |

## 8. Requirement Presentation

### 8.1 Compact Requirement Summary

One line: `<ID (monospace)>` — `<Title>` — `<Status/Classification badge>` — one-sentence behavior statement. Used in requirement-index tables and the PRS functional catalog's table rows.

### 8.2 Full Requirement Card

Per DSF-001 §E.8, in field order:

1. **Header row:** ID + Title, Sage Gold rule beneath.
2. **Status/Classification badge** (§7.1 badge treatment, DSF-001 §F).
3. **Priority** (where the controlling source states one).
4. **Controlling source display:** monospace ID(s), e.g. `DS-RSK-001`, hyperlinked to the source volume/section.
5. **Purpose/Description.**
6. **Acceptance Criteria** (§7.2 standalone treatment, in card context).
7. **Edge Cases** (§7.2 standalone treatment, in card context).
8. **Dependencies:** monospace ID list.
9. **Testing** (§7.2 standalone treatment, in card context).
10. **Traceability state:** Pending/Complete per stage (§7.2 Pending Traceability where applicable).

**Mandatory disclaimer, every card:** "This card is a derived summary. The controlling requirement text in the cited Codex volume governs." (Restates DSF-001 §A.2.1/§A.2.2, DSF-002 §2.)

### 8.3 Classification and Status Badges

Exactly as DSF-001 §F: Sage Gold fill = Committed/MVP; Soft-Gray outline = Planned; dashed outline = Future/Exploratory. Text label always present alongside the shape (§2.5).

## 9. Accessibility

1. **Contrast:** Per §2.3, WCAG 2.2 AA minimum (4.5:1 normal text, 3:1 large text/UI), targeting AAA (7:1) for primary body text where achievable.
2. **Minimum practical text sizes:** Body 10pt minimum in print/PDF; captions/metadata 8pt minimum; no functional text below 8pt at any zoom-independent (print) size.
3. **Meaningful headings:** Every heading level used in document order (no skipped levels, DSF-001 §D.7); headings describe content, never generic labels like "Section 1."
4. **Alt text:** Every diagram/figure carries the accessibility description already required per-diagram in DSF-001 §G's "Accessibility Text Requirement" column and this document's Diagram Register (`docs/publication/DIAGRAM_REGISTER.md`) — never omitted, never a placeholder left unfilled in a released artifact.
5. **Accessible table structure:** Every table has a header row; header cells are marked as header cells (not merely bold text) in any format that supports true table semantics (DOCX/HTML); no table conveys structure through visual spacing alone.
6. **No color-only meaning:** Every color-coded element (§2.2, §7, §8.3) carries a text label or icon (restates DSF-001 §C.2 rule 3).
7. **Printable grayscale support:** §2.5.
8. **Diagram descriptions:** Full sentence-form accessibility text per diagram (not a one-word alt tag) — see `docs/assets/diagrams/README.md` (DSF-001 §H.3's approved diagram-source location) and the Diagram Register (`docs/publication/DIAGRAM_REGISTER.md`).
9. **Clear link text:** Cross-references use the descriptive form "`<ID>` — `<Title>`" rather than bare "click here"/"see here" link text.
10. **Readable code blocks:** Monospace, light panel, Steel-Gray border (§3.1, DSF-001 §D.4), never a full-bleed dark block on a light body page.

## 10. Document-Family Variants

| Aspect | Executive Product Plan | PRS | Codex Volume | Codex Master Edition |
|---|---|---|---|---|
| Cover treatment | Obsidian/Charcoal dark cover, Highlight Gold title, motto "Wisdom Over Noise" prominent | Obsidian/Charcoal dark cover, restrained (no motto emphasis — working document tone) | Volume-numbered divider per DSF-001 §E.5 within the master edition; standalone volume cover if released individually | Master cover + one E.5 divider per volume |
| TOC depth | H1–H2 (DSF-001 §E.4, kept lean for 25–45pp target) | H1–H3 | H1–H3 | H1–H3, plus a master volume index |
| Requirement presentation | Compact summaries only (§8.1); no full requirement cards | Full requirement cards (§8.2) in the functional catalog | Full requirement text, verbatim from source — no card abstraction (a Codex volume page is the Codex text itself, not a derived summary) | Same as individual volumes |
| Callout density | Sparse — Product Principle, Advisory AI, Fail Closed, Example, Founder-tier Risk/Safety-Boundary only, to preserve narrative readability | Full callout catalog (§7) as needed per section | Full callout catalog as needed | Full callout catalog as needed |
| Diagram density | High — most diagrams from the Diagram Register's Illustrative/Conceptual classes | Moderate — Normative diagrams tied to cited requirements | As already present in source volumes; no new diagrams invented at publication time | Same as individual volumes |
| Disclaimer page (DSF-001 §E.3) | Required | Optional (governance-decided) | Not applicable (volume-level, not publication-level, disclaimers) | Front-matter only, once |
| Target length | 25–45pp | 80–150pp | Per volume, as authored | 500+pp |

## Non-Goals

DSF-003 does not: select a page-size default without an A4 fallback path (§4.1 defines both); introduce any palette value, functional color, page type, or component not already named or explicitly extended per §7.2/§8; commit to a specific font license; or generate any DOCX/PDF artifact.

## Dependencies

- [DSF-001 — DarkSage Publication Architecture](DARKSAGE_PUBLICATION_ARCHITECTURE.md) §A, §C–§I
- [DSF-002 — DarkSage Product Requirements Specification](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) §2, §21
- `docs/standards/BRAND_GUIDE.md`, `DIAGRAM_STANDARD.md`, `DOCUMENTATION_STANDARD.md`, `STYLE_GUIDE.md`
- `docs/publication/templates/` (Deliverable 2, this batch)
- `docs/publication/DIAGRAM_REGISTER.md` (Deliverable 3, this batch)

## Risks and Constraints

- **Font availability unverified in the eventual generation environment** — restates DSF-001's own open item; §3.1's fallback stack is the actually-portable option set, but final selection is deferred to generation-tooling implementation, which must record whichever font it actually used (§3.1).
- **CMYK/print-safe values are computed, not independently proofed on a physical press** — §2.4's print-safe alternatives are a generation-time computation from the sRGB values; a physical print proof remains a future verification step, not claimed as complete here.

## Verification Approach

Unique-ID check (`DSF-003` against all existing `DSF-NNN`/`DS-NNN`/`DS-<DOMAIN>-NNN`/`ADR-NNN`/`DSCP-NNN`/`DR-NNN` namespaces); cross-reference resolution against DSF-001/DSF-002; confirmation that every hex value matches DSF-001 §C.1 exactly; confirmation that no new callout in §7.2 contradicts a DSF-001 §F entry; confirmation that no Codex volume, ADR, or root governance file was modified.

## References

- [DSF-001 — DarkSage Publication Architecture](DARKSAGE_PUBLICATION_ARCHITECTURE.md)
- [DSF-002 — DarkSage Product Requirements Specification](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md)
- `docs/standards/BRAND_GUIDE.md`, `DIAGRAM_STANDARD.md`, `DOCUMENTATION_STANDARD.md`, `NAMING_AND_ID_STANDARD.md`, `STYLE_GUIDE.md`, `WRITING_GUIDE.md`

## Appendix A — Open Questions

1. **Font licensing/embedding verification** — carried over from DSF-001; not resolved by this document (§3.1, Risks and Constraints).
2. **Print-proof verification** — carried over from this document's own Risks and Constraints; a physical/vendor print proof of the CMYK-safe values has not been performed.
