# DSF-001 — DarkSage Publication Architecture

## Document Control

| Field | Value |
|---|---|
| Document ID | DSF-001 |
| Title | DarkSage Publication Architecture |
| Version | 0.2.0 |
| Status | Draft |
| Owner | TheSinnerMan |
| Contributors | |
| Classification | Internal |
| Repository | LightSwornPVP/DarkSage |
| Created | 2026-07-25 |
| Last Updated | 2026-07-25 |
| Source Baseline Commit | ec3a4ed (docs: complete DarkSage Codex consolidated cleanup) |
| Controlling Sources | DS-001 through DS-014 (Approved/Draft as recorded in each volume); ADR-001–004; `docs/standards/*`; `docs/CODEX_INDEX.md` |
| Publication Relationship | Governs the production of [DSF-002 — DarkSage Product Requirements Specification](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md), the DarkSage Executive Product Plan (not yet authored), and the Codex Complete Edition. Does not itself contain product requirements, and is itself subordinate to the controlling Codex and root public Markdown for all product, engineering, safety, security, lifecycle, classification, and architecture meaning — see §A. |

Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.

### Document ID Rationale

`docs/standards/NAMING_AND_ID_STANDARD.md` authorizes `DSF-NNN` ("DarkSage Flagship Publication Document") as a repository-wide-unique, publication-only controlled-document-ID namespace, distinct from `DS-NNN` (Codex volumes), `DS-<DOMAIN>-NNN` (requirements within those volumes), `ADR-NNN` (architecture decisions), `DSCP-NNN` (change proposals), and `DR-NNN` (design reviews). This document, `DSF-001`, is the first document in that namespace; `DSF-002` (the Product Requirements Specification) is the second. Per the naming standard's authority boundary for this namespace, a `DSF-NNN` document is publication-only: it does not create `DS-<DOMAIN>-NNN` requirements, does not supersede Codex or root governance, and cannot establish product classification, implementation commitment, or architecture authority independently — see §A below for the full authority hierarchy.

## Revision History

| Version | Date | Author | Summary |
|---|---|---|---|
| 0.1.0 | 2026-07-25 | TheSinnerMan | First controlled draft. Establishes the publication authority model, the three flagship-document-family roles, the DarkSage visual identity (Obsidian/Charcoal/Steel/Ivory/Sage Gold), the typography system, the page and component systems, the initial diagram inventory, the generation/publication workflow, quality gates, and planned outputs. Authored alongside [DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) in the same batch. No Word/PDF artifact generated in this pass. |
| 0.2.0 | 2026-07-25 | TheSinnerMan | Targeted Critical/High repair (FLAG-H01–H04) following independent audit. **FLAG-H01:** §A rewritten from a single "Markdown is authoritative" framing into an explicit three-tier publication authority hierarchy (controlling Codex/root Markdown → `DSF-NNN` Markdown → generated DOCX/PDF), removing the prior ambiguity that could be read as granting `docs/publication/`/`docs/requirements/` the same requirement-originating authority as `docs/codex/`. **FLAG-H02:** Document ID Rationale updated to cite `DSF-NNN`'s now-formal authorization in `docs/standards/NAMING_AND_ID_STANDARD.md` (see that document's own revision history) rather than claiming self-reservation. Non-blocking fixes: §F's "Evidence / Conflict" component-name cell changed from a backslash-escaped pipe to a slash, removing any table-parsing ambiguity across renderers; §D's font wording no longer asserts unverified "safely embeddable" licensing status for Aptos/Aptos Display/Consolas, restated as preferred-candidate typefaces subject to availability/licensing/embedding/export-toolchain verification, with fallback-stack wording corrected to match. No Codex volume, ADR, product requirement, or safety/pipeline/roadmap/backlog/idea content changed. |

## 1. Purpose

DSF-001 defines the visual, structural, production, and authority model for the three DarkSage flagship document families — the DarkSage Executive Product Plan, the DarkSage Product Requirements Specification, and the DarkSage Codex — Complete Edition — so that future Word/PDF generation work has a single, controlled specification to build against rather than ad hoc formatting decisions made per document.

DSF-001 does not itself generate a Word or PDF artifact. It is a planning and governance document: it defines *how* publication will work and *what it must never do to the underlying Codex*, so that when generation work begins, it proceeds against an approved plan rather than improvised choices.

## 2. Scope

This document governs: the authority relationship between Markdown source and generated Word/PDF editions; the role and audience of each flagship document family; the DarkSage visual identity (palette, typography); the page, component, and diagram systems used across all three families; the generation/publication workflow and artifact-naming/versioning convention; and the quality gates a publication must pass before release.

This document does not govern: the content of DS-001 through DS-014 or any ADR (those remain independently authoritative per their own volumes, and per §A's tier 1); the product/engineering meaning DSF-002 summarizes (governed exclusively by tier 1 per §A — DSF-002 governs only its own publication-tier presentation of that meaning, per tier 2); backlog or idea promotion (DS-013/DS-014 remain the sole authority for that); or the DarkSage product's own UI/UX system (DS-007, which governs the *product's* interface, not this document's publication interface).

## 3. Audience

Contributors producing Word/PDF editions of DarkSage's controlled documentation, independent auditors verifying a publication's fidelity to its Markdown source, and future Codex authors who need to know how a new volume or diagram fits into the publication system.

## 4. Definitions

See DS-001 §24 and DS-002 §4 for foundational Codex terms. Additional terms used in this document:

| Term | Meaning |
|---|---|
| Publication artifact | A generated Word (.docx) or PDF edition of one or more controlled Markdown documents |
| Presentation Independence (publication sense) | The publication-tier analogue of ADR-004: visual formatting, layout, and pagination choices never create, remove, reclassify, or reinterpret a requirement's meaning or classification |
| Flagship document family | One of the three publication targets this architecture governs: Executive Product Plan, Product Requirements Specification, Codex Complete Edition |
| Generation pipeline | The (not-yet-built) toolchain that transforms approved Markdown source into DOCX/PDF publication artifacts per §H |
| Publication manifest | A machine-readable record, per publication run, of source version, generation date, publication version, and included documents (§H, §J) |

## A. Publication Authority Hierarchy

FLAG-H01 repair note: the prior version of this section stated a single "Markdown is authoritative" rule that treated `docs/codex/`, `docs/publication/`, and `docs/requirements/` as one undifferentiated authoritative tier. That framing was ambiguous — it could be misread as granting `docs/publication/`/`docs/requirements/` (the `DSF-NNN` namespace) the same requirement-originating authority as `docs/codex/`. This section replaces it with an explicit three-tier hierarchy.

### A.1 The Three Tiers

1. **Controlling Codex and root public Markdown.** DS-001 through DS-014, ADR-001 through ADR-004, and the root-level governance documents (`SECURITY_RULES.md`, `TRADING_RULES.md`, `ARCHITECTURE.md`, `PROJECT_SPEC.md`, `ROADMAP.md`, `AGENTS.md`). This tier is the **sole authority** for product meaning, engineering meaning, safety, security, lifecycle, Release Classification, architecture, and requirements meaning. No `DSF-NNN` document, and no generated publication artifact, may originate, override, reinterpret, reclassify, or independently govern any of that meaning.
2. **`DSF-NNN` Markdown** (this document and DSF-002). Authoritative **only** for: publication architecture; publication workflow; visual and layout rules; and the exact derived-summary wording within the `DSF-NNN` document itself. A `DSF-NNN` document does not originate a product or engineering requirement, and its own compressed restatement of a Codex requirement is never a second, independent source for that requirement's meaning.
3. **Generated DOCX/PDF publication artifacts.** Subordinate to their `DSF-NNN` Markdown source for publication text and layout; and, for any product or engineering meaning that source text itself summarizes, also subordinate to tier 1 — exactly as the `DSF-NNN` Markdown source already is. A publication artifact never acquires authority its Markdown source does not have.

### A.2 Required Effects

1. **`docs/publication/` and `docs/requirements/` never originate product requirements.** Every requirement, classification, ADR decision, and piece of normative product/engineering content originates in and is governed exclusively by tier 1 — the Markdown files under `docs/codex/` and the root-level governance documents. Files under `docs/publication/` and `docs/requirements/` (the `DSF-NNN` namespace) restate and consolidate tier-1 content for publication purposes; they never originate it. This restates DS-001 §23 and `docs/standards/DOCUMENTATION_STANDARD.md` §1 at the publication-production level with the ambiguity removed; it does not introduce a second source-of-truth doctrine.
2. **DSF-002 is a derived consolidation, not independent requirement authority.** It creates no requirement, classification, or architecture authority of its own — see DSF-002 §2 "Relationship to the Codex" for the corresponding statement in that document.
3. **Publication formatting shall never create, remove, reclassify, reinterpret, or override a requirement, its classification, capability state, evidence access, or authority.** A requirement's ID, title, Release Classification (Committed/MVP, Planned, Future/Exploratory), priority, acceptance criteria, and Governing Source citations must appear in a publication artifact exactly as they appear in tier 1. Visual emphasis (color, callout style, page placement) may highlight a requirement's classification but may never change it, imply a different one, or omit it.
4. **When a `DSF-NNN` summary conflicts with a controlling Codex requirement, the Codex requirement governs.** The conflicting `DSF-NNN` summary is a defect in that document to be corrected or regenerated — never a competing interpretation, and never resolved in the `DSF-NNN` document's favor.
5. **When a generated DOCX/PDF conflicts with its `DSF-NNN` Markdown source, the Markdown source governs publication text and layout.** Where that conflict instead concerns product or engineering meaning rather than publication text/layout, tier 1 governs, exactly as it already governs the Markdown source itself.
6. **Generated editions identify their own provenance.** Every publication artifact's document-control page (§E) states: source repository, source baseline commit (or tag), source document version(s), generation date, and publication version — so a reader can always trace a printed page back to the exact Markdown revision that produced it.
7. **Presentation Independence extends to publication.** Just as ADR-004 prohibits DarkSage's product UI from using widget visibility to gate capability, this architecture prohibits publication layout (page breaks, section reordering for visual flow, cover treatment) from changing which requirements exist, what they say, how they are classified, what capability state they represent, or what evidence access they describe. A publication's visual design is a view into the Codex; it is never the Codex, and it is never the `DSF-NNN` document either — only a rendering of it.

## B. Flagship Document Roles

### B.1 DarkSage Executive Product Plan

- **Purpose:** A concise, visual, approachable product narrative communicating DarkSage's vision, differentiation, user experience, architecture overview, safety philosophy, roadmap, and example assessments.
- **Audience:** Partners, prospective contributors, reviewers, and non-specialist stakeholders.
- **Authority:** Zero independent requirement authority. Every factual/normative claim in the Executive Product Plan must trace to DS-001 (vision, philosophy), DS-011 (roadmap), or [DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) (consolidated requirements). It does not replace the PRS or the Codex; a reader needing the actual product contract is directed to DSF-002.
- **Target length:** Approximately 25–45 polished pages.
- **Status:** Not yet authored. This architecture defines its role and visual treatment in advance so its eventual authoring proceeds against an approved plan (§J).

### B.2 DarkSage Product Requirements Specification

- **Purpose:** A consolidated, practical product/build contract covering product behavior, scope, acceptance expectations, user flows, nonfunctional requirements, safety, lifecycle, and traceability.
- **Audience:** Product, engineering, design, QA, security, and implementation planning.
- **Authority:** Derived from the Codex; references controlling `DS-<DOMAIN>-NNN` and `ADR-NNN` IDs rather than creating a second, independent requirement authority. See [DSF-002](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md) §"Authority and Derivation" for the exact rule.
- **Target length:** Approximately 80–150 polished pages, depending on final layout.
- **Status:** Authored in this same batch as this document (v0.1.0, Draft).

### B.3 The DarkSage Codex — Complete Edition

- **Purpose:** The full 14-volume controlled suite (DS-001 through DS-014), for architecture, engineering, security, QA, governance, and long-term maintenance use.
- **Audience:** Architecture, engineering, security, QA, governance, and future Codex authors.
- **Authority:** The Codex itself — DS-001 through DS-014 as already authored and approved/drafted. The Complete Edition changes no content; it packages the existing volumes with indexes, divider pages, controlled metadata, glossary, cross-references, an ADR catalog, a requirement index, and a traceability appendix.
- **Production form:** May be produced as fourteen individual volume editions and one master edition (§J).
- **Estimated length:** Likely 500+ polished pages depending on final layout and diagram density.
- **Status:** Source content (DS-001–DS-014) exists and is committed; the publication (DOCX/PDF) editions do not yet exist.

## C. DarkSage Visual Identity

### C.1 Primary Palette

| Name | Hex | Role |
|---|---|---|
| Obsidian Black | `#0B0B0D` | Covers, divider pages, dark UI chrome |
| Charcoal Gray | `#17181C` | Secondary dark surface, cover sub-panels |
| Steel Gray | `#2A2D33` | Structural lines, table borders on dark surfaces |
| Soft Gray | `#A7ABB3` | Secondary/muted text, captions, metadata rows |
| Ivory White | `#F4F2EC` | Body page background, light-mode primary surface |
| Sage Gold | `#C8A45D` | Restrained hierarchy accent: section rules, requirement IDs, selected-state emphasis |
| Highlight Gold | `#E0BE72` | Premium emphasis only — cover titles, key-decision callouts, volume-divider numerals |

### C.2 Rules

1. Gold is restrained. It marks hierarchy, premium emphasis, selected states, key decisions, and branding — never body text, never table fill, never used decoratively on every page.
2. Gold never replaces a functional status color. Green (validated/pass), red (risk/blocker/fail), amber (warning/caution), and blue (informational/state) remain available and required for financial, safety, severity, validation, and state meaning, per §F's component system.
3. Color is never the sole carrier of meaning. Every color-coded element (status badge, severity marker, classification tag) also carries a text label or icon, consistent with `docs/standards/BRAND_GUIDE.md`'s accessibility rule and DS-NFR-004/DS-UX-017's product-level accessibility principle applied here at the publication level.
4. Body pages favor readability over decorative darkness. Long-form PRS and Codex body pages use Ivory White or a warm-light background with dark (near-Obsidian) text and Sage Gold structural accents (rules, requirement-ID chips, section numerals) — not dark backgrounds with light text.
5. Dark covers and divider pages may use Obsidian/Charcoal freely; body content pages may not.
6. Accessible contrast is mandatory: body text against Ivory White meets at least WCAG 2.2 AA contrast (the same standard DS-NFR-004/DS-UX-017 name as the product's own target, applied here to publication typography); Sage Gold is never used for body-text-sized content on a light background without a contrast check, since gold-on-ivory is a lower-contrast pairing than dark-on-ivory.
7. Visual tone is premium, disciplined, precise, trustworthy, restrained. Sage/thematic imagery (DS-001 §17's themed vocabulary) is used subtly — a wordmark, a restrained motif — never as decorative "fantasy" illustration that would undercut DS-001 §8.1's Clarity value or the Brand Principle "Wisdom Over Noise."

### C.3 Logo

Per `docs/standards/BRAND_GUIDE.md`: until an approved logo asset exists, publications use the wordmark **DarkSage** set in the display typeface (§D.1). No unofficial or placeholder logo mark is substituted.

## D. Typography System

Per `docs/standards/STYLE_GUIDE.md`, the preferred candidate publication fonts are Aptos Display/Aptos (headings/body) and Consolas (code), commonly distributed with Microsoft Office/Windows environments. These are named as preferred candidates only: their availability, licensing, embedding rights, and compatibility with whatever export toolchain is eventually selected (§H) have not been verified for this repository's publication use case and must be confirmed before generation begins. No font file is committed to the repository; publication tooling references these fonts by name and falls back per §D.6 to a stack confirmed legally available in the target generation environment.

### D.1 Display / Cover Typography

- Typeface: Aptos Display, weight Bold/Semibold.
- Use: Cover titles, volume-divider numerals and titles, Executive Product Plan section openers.
- Case: Title Case for document titles; avoid all-caps except for the short "DARKSAGE" wordmark treatment on covers.
- Color: Ivory White or Highlight Gold on Obsidian/Charcoal cover backgrounds only (§C.2 rule 5).

### D.2 Section-Heading Typography

- Typeface: Aptos Display, weight Semibold.
- Hierarchy: H1 (document title, one per document per `docs/standards/STYLE_GUIDE.md` §Headings) → H2 (numbered major section) → H3 (numbered subsection) → H4 (requirement/entry title, used sparingly).
- Numbering: Numbered H2/H3 for controlled Codex-derived content, matching the existing Markdown source's own numbering exactly — publication numbering is never renumbered independently of the source.
- Color: Near-Obsidian on light body pages, with a Sage Gold rule or numeral accent; never gold-on-gold or low-contrast combinations.

### D.3 Body Typography

- Typeface: Aptos, Regular, target 10–11pt for print/PDF body text.
- Line length: Target 70–90 characters per line for print columns, consistent with standard readability practice; the Codex Complete Edition's denser reference tables may run wider within a table's own bounded width.
- Weight/emphasis: Bold for defined terms on first use and for **shall**/**should**/**may** normative keywords per `docs/standards/DOCUMENTATION_STANDARD.md` §6, restating the Markdown source's own emphasis rather than inventing new emphasis.

### D.4 Monospace / Code Typography

- Typeface: Consolas.
- Use: File paths, requirement IDs when shown inline in body prose (e.g., `DS-RSK-001`), code/config blocks, the canonical `TradeValidationPipeline` stage list when reproduced verbatim.
- Background: Light gray or Ivory-tinted panel with a thin Steel Gray border, never a full-bleed dark block on a light body page (readability over decorative darkness, §C.2 rule 4).

### D.5 Table Typography

- Typeface: Aptos, Regular, target 9–10pt (one step below body) to fit dense requirement/traceability tables without excessive width.
- Header row: Aptos Semibold, Steel Gray or Sage Gold rule beneath, never gold fill behind header text (contrast).
- Numeric alignment: Right-aligned for numeric columns (version numbers, thresholds, counts); left-aligned for text columns.

### D.6 Fallback Fonts

Where Aptos/Aptos Display are unavailable — or their licensing/embedding rights are not confirmed for a given generation environment — fall back to Calibri/Calibri Light (heading) and Calibri (body); where Consolas is unavailable or unconfirmed, fall back to Courier New. The approved fallback stack must use only fonts legally available (installed, licensed, or otherwise rights-cleared) in the target generation environment; fallback availability does not itself constitute a licensing or embedding-rights verification for the preferred candidate typefaces. No proprietary font binary is ever committed to or distributed from this repository, regardless of which typeface in the stack is ultimately used.

### D.7 Rules for Capitalization, Weights, Spacing, Line Length, Hierarchy

- Capitalization: Sentence case for body prose and most headings; Title Case reserved for document/volume titles and cover treatment.
- Weight: No more than two weights (Regular, Semibold/Bold) per typeface family in a single document — avoids visual noise inconsistent with the Restraint value (DS-001 §8.7).
- Spacing: Generous whitespace on cover/divider pages (§E.1, §E.4); body pages favor readable margins over cramped density, per §E's grid rules.
- Line length: See §D.3.
- Hierarchy: Exactly one H1 per document (matching `docs/standards/STYLE_GUIDE.md` §Headings); heading levels never skip (H2 → H4 without an intervening H3 is not used).

## E. Page Systems

For each page type below: header, footer, page number, document ID, version, classification, title hierarchy, margins, grid, whitespace rules, table behavior, and cross-reference style.

### E.1 Cover Page

- **Header/Footer:** None (cover carries no running header/footer).
- **Page number:** Not shown (covers are unnumbered or numbered separately from body — roman numeral or omitted, per generation-tool convention fixed at implementation time).
- **Content:** Document ID, title, version, status, owner, classification, motto ("Wisdom Over Noise"), and generation/publication metadata footer block (source version, generation date, publication version — §A.5).
- **Margins/grid:** Wide, symmetric margins; generous whitespace per `docs/standards/BRAND_GUIDE.md` §Covers.
- **Background:** Obsidian Black or Charcoal Gray permitted (§C.2 rule 5); title in Highlight Gold or Ivory White.
- **Cross-reference style:** N/A (cover carries no cross-references).

### E.2 Document-Control Page

- **Header/Footer:** Standard running header/footer begins here (document short title + document ID in header; page number + classification in footer).
- **Content:** The exact Document Control table from the Markdown source (Document ID, Title, Version, Status, Owner, Contributors, Classification, Repository, Created, Last Updated, plus any source-specific fields), reproduced verbatim — never summarized or reworded.
- **Margins/grid:** Standard body margins (§E.5).
- **Table behavior:** Full-width two-column key/value table; never split across a page break mid-row.

### E.3 Legal / Disclaimer Page (where applicable)

- **Content:** Non-committal, non-promissory language consistent with DS-001 §21's non-goals (no profit guarantee, no prediction-accuracy claim, educational/decision-support positioning) and DS-002 §9. This page never introduces a claim beyond what DS-001/DS-002 already establish — it restates their non-goals in publication-appropriate prose, it does not add new ones.
- **Placement:** Immediately after the document-control page, before the table of contents, on any flagship publication intended for external (partner/reviewer) distribution — required for the Executive Product Plan, optional (governance-decided) for internally-distributed PRS/Codex editions.

### E.4 Table of Contents

- **Structure:** Generated from the document's own heading hierarchy (§D.7); never hand-maintained separately from the source headings, to avoid drift.
- **Depth:** H1–H2 for the Executive Product Plan (kept lean, per its 25–45 page target); H1–H3 for the PRS and Codex volumes.
- **Cross-reference style:** Page-number-linked entries; bookmarked in PDF/DOCX for click-through navigation (§I).

### E.5 Volume Divider

- **Use:** Codex Complete Edition only, one per volume (DS-001–DS-014), separating volumes within the master edition.
- **Content:** Large volume numeral (Roman, per `docs/CODEX_INDEX.md`'s existing Volume I–XIV numbering), volume ID (`DS-NNN`), volume title, one-sentence scope summary drawn from the volume's own §1 Purpose.
- **Background:** Obsidian Black or Charcoal Gray, numeral in Highlight Gold (§C.2 rule 5).
- **Page number:** Continues the master edition's running numbering; divider pages are numbered like any other page for reference purposes, even though visually distinct.

### E.6 Chapter Opener

- **Use:** Each numbered H2 section within a volume/document that begins a substantial content block (e.g., DS-002 §6 "Cross-Cutting Product Requirements").
- **Content:** Section number and title in Display typography (§D.1/D.2), a one-sentence scope line drawn from the source, generous top whitespace before body content begins.
- **Margins/grid:** Standard body margins; extra top margin (roughly 1.5–2× a normal page's top margin) for visual separation.

### E.7 Normal Content Page

- **Header:** Document short title (left) + Document ID (right).
- **Footer:** Page number (center or outer edge, generation-tool convention) + Classification (opposite corner from page number).
- **Margins/grid:** Standard single-column body text; tables may span full text width.
- **Whitespace:** Standard paragraph spacing; no compressed "fit more on the page" spacing that would harm readability (§C.2 rule 4).
- **Cross-reference style:** In-text citations use the exact controlled ID (`DS-RSK-001`, `ADR-002`) in monospace (§D.4), hyperlinked to the corresponding section/page within the same publication artifact where the target exists in it, or annotated with its source volume where it does not (e.g., a PRS page citing a DS-004 requirement not itself reproduced in the PRS).

### E.8 Requirement Page / Card

- **Use:** Presenting one `DS-<DOMAIN>-NNN` requirement (Codex Complete Edition) or one consolidated PRS entry (§9 of DSF-002).
- **Structure (component, detailed in §F "Requirement Card"):** ID + Title header row (Sage Gold rule beneath), Release Classification badge (§F "Status/Classification Badge"), Priority, Purpose, Description, Acceptance Criteria (bulleted), Edge Cases (bulleted), Governing Source/Dependencies (monospace ID list), Testing.
- **Page-break behavior:** A requirement card's ID/Title header and its Release Classification badge never separate from the start of its own body content across a page break; the card as a whole may span a page break mid-body if it does not fit, but its header block stays attached to at least its first content line ("widow/orphan" control for requirement cards specifically).

### E.9 ADR Page

- **Structure:** Mirrors `docs/templates/markdown/ADR.md`'s existing section order (Document Control, Context, Decision, Consequences, Alternatives Considered, Related Requirements, Decision History) exactly — publication never reorders an ADR's own section sequence.
- **Emphasis:** The **Decision** statement itself is set in a distinguished callout (§F "Deterministic Authority Callout" or a dedicated ADR-Decision treatment) since it is the single most load-bearing sentence on the page.

### E.10 Diagram Page

- **Structure:** Diagram title + ID (top), diagram image/render (center), legend (where symbols are non-obvious, per `docs/standards/DIAGRAM_STANDARD.md`), source-volume citation and accessibility description (bottom), figure caption (§F "Figure Caption").
- **Placement:** A diagram never spans a page break; if it cannot fit on one page at readable scale, it is presented as a fold-out/landscape page or split into an explicitly labeled multi-part figure (Figure N.1, N.2), never silently cropped.

### E.11 Appendix Page

- **Structure:** Standard content-page treatment (§E.7) with an "Appendix A/B/..." running header addition, matching the source document's own Appendix lettering exactly.

### E.12 Glossary / Index Page

- **Structure:** Two-column dense-table layout (term/definition, or term/page-reference) permitted for space efficiency, using Table Typography (§D.5); this is the one page type where denser layout is appropriate, since a glossary/index is a lookup tool, not a reading-flow page.

### E.13 Revision-History Page

- **Structure:** The exact Revision History table from the Markdown source (Version, Date, Author, Summary), reproduced verbatim in full — including repair-pass summaries — never abbreviated to "minor fixes" or similar. This preserves the Codex's own audit trail in the published edition.

## F. Component System

| Component | Visual Treatment | Use |
|---|---|---|
| Product principle callout | Ivory panel, Sage Gold left-rule, Sage Gold small-caps label "PRINCIPLE" | DS-001 Constitution items, foundational principles |
| Safety boundary callout | Ivory panel, Risk-Red left-rule, red small-caps label "SAFETY BOUNDARY" + icon | ADR-002-class content (Sage cannot bypass Risk Engine), TradeValidationPipeline integrity statements, fail-closed rules |
| Deterministic authority callout | Ivory panel, Steel-Gray left-rule, label "DETERMINISTIC" | ADR-003-class content, deterministic-calculation statements |
| Research / non-committed callout | Ivory panel, dashed Soft-Gray border, label "NON-COMMITTED — RESEARCH REFERENCE" | DS-014 idea entries, any content citing a third-party model/reference under DS-IDG-004 |
| Open question | Ivory panel, amber left-rule, label "OPEN QUESTION" | Appendix A entries genuinely unresolved in the source |
| Risk / warning | Ivory panel, Risk-Red left-rule + warning icon, label "RISK" | Material risk disclosures, DS-001 §13-class content |
| Note | Ivory panel, Soft-Gray left-rule, label "NOTE" | Non-normative clarifying remarks |
| Requirement card | Per §E.8 | Individual requirement presentation |
| Acceptance criteria | Bulleted checklist glyphs (not colored checkmarks implying "done" — these are criteria, not status) | Within requirement cards |
| Edge cases | Bulleted list, slightly indented/smaller than acceptance criteria to signal secondary detail | Within requirement cards |
| Implementation notes | Italic, Soft-Gray text | Within requirement cards, where present in source |
| Testing expectations | Monospace label "TESTING:" + description | Within requirement cards |
| Status / classification badge | Pill-shaped label: Sage Gold fill for Committed/MVP, Soft-Gray outline for Planned, dashed outline for Future/Exploratory — always paired with the text label itself (never color alone, §C.2 rule 3) | Requirement cards, backlog/idea entries |
| Lifecycle diagram | Horizontal stage flow, Steel-Gray connective arrows, stage boxes in Ivory with Obsidian text | Strategy promotion lifecycle, backlog promotion lifecycle, DS-UX-016 interface state lifecycle |
| Traceability link | Monospace ID, underlined, resolves to the cited requirement/ADR/design/test/release entry per `docs/traceability/TRACEABILITY_MATRIX.csv`'s five-stage model | Any cross-reference to another controlled ID |
| Evidence / contradiction panel | Two-column panel (Evidence / Conflict), amber header if a genuine conflict is disclosed | Sage evidence-conflict disclosure (DS-SGE-009), audit-finding contradiction records |
| Example trade assessment | Bordered example panel, clearly labeled "ILLUSTRATIVE EXAMPLE — NOT LIVE DATA" in the panel header, never using the same visual treatment as a live/authoritative data surface | Executive Product Plan and PRS §10 user-journey illustrations |
| Code / config block | Consolas monospace, light panel with Steel-Gray border (§D.4) | File paths, pipeline stage lists, example payloads |
| Table | Per §D.5 | General tabular content |
| Figure caption | Aptos Regular, 9pt, below the figure, format "Figure N — Title" | All diagrams/images |

## G. Diagram Inventory

For every diagram: purpose, source volumes, authoritative labels, intended placement(s), conceptual/normative/illustrative classification, and required accessibility text.

| # | Diagram | Purpose | Source Volumes | Authoritative Labels | Placement(s) | Type | Accessibility Text Requirement |
|---|---|---|---|---|---|---|---|
| 1 | DarkSage product ecosystem | Show how market data, Scanner, Signals, Charts, Strategy, Portfolio, Sage, and Auto-Trader relate as one platform | DS-001 §4; PROJECT_SPEC.md §1 | Themed + plain labels per DS-001 §17 mapping | Executive Product Plan, PRS §3, Codex DS-001 divider | Illustrative | Describe the ecosystem as a set of connected capability areas around a shared backend, without implying any capability not yet Committed/Planned |
| 2 | Authority hierarchy | Show the six-tier conflict-resolution hierarchy (root safety governance → owner decisions → ADRs → Codex volumes → implementation docs → local workflow files) | DS-012 §7 (DS-ADR-010) | Exact six tier names from DS-ADR-010 | PRS §21, Codex DS-012 | Normative | State each tier's name and rank in reading order; state explicitly that no lower tier may override a higher one |
| 3 | Canonical trade-validation pipeline | Show the exact 12-stage `TradeValidationPipeline` | ARCHITECTURE.md §14; DS-ARC-011; DS-EXE-001; DS-API-EXE-001 | Exact stage names/order from `docs/pipeline-stages.txt` — no renaming, reordering, or omission | PRS §11, Codex DS-004/DS-002/DS-006, Executive Product Plan (safety section) | Normative | List all 12 stages in exact order as the accessible text equivalent, since the diagram's meaning depends entirely on order |
| 4 | Backend-authoritative architecture | Show client/server topology: desktop + mobile as clients, backend as sole authority over trading/account state | DS-ARC-001; ARCHITECTURE.md §2 | "Backend-authoritative," "Client," never "peer" | PRS §6, Codex DS-004 | Normative | State that clients read/display backend-computed state and never independently compute or store authoritative trading state |
| 5 | Sage advisory boundary | Show Sage's position relative to the Risk Engine and Execution Engine: advises, cannot bypass, cannot call | ADR-002; DS-003 Core Rule; DS-PRD-006 | "Sage advises," "Risk Engine — independent authority," "no direct call" | Executive Product Plan, PRS §11/§13, Codex DS-003/DS-012 | Normative | State explicitly that no arrow exists from Sage directly to Execution Engine or Broker Adapter under any circumstance |
| 6 | Deterministic-versus-AI responsibility split | Show which calculations are deterministic-only (risk, backtests, indicators, portfolio math) versus where AI may contribute (explanation, synthesis, tutoring) | ADR-003; DS-PRD-004; DS-001 §9/§12 | "Deterministic (authoritative)" vs. "AI (advisory)" | PRS §11/§13, Executive Product Plan | Normative | State that deterministic items never accept generative model output as their authoritative value |
| 7 | Provider abstraction model | Show market-data, broker, and AI provider adapters behind a common interface, with the interface as the only thing consuming code touches | DS-ARC-006; DS-EXE-006; DS-ARC-013; DS-PRD-001 | "Adapter," "Provider," "Common Interface" | PRS §12/§13, Codex DS-004 | Normative | State that consuming code depends on the interface, not on any named vendor |
| 8 | Market-data and provenance flow | Show data flow: Provider → Adapter → Normalizer → Cache/Database → consuming feature, with data-state labeling attached throughout | ARCHITECTURE.md §7; DS-ARC-006; DS-PRD-008 | "Provider," "Adapter," "Normalizer," data-state labels (current/delayed/stale/historical/simulated) | PRS §12, Codex DS-004 | Normative | State that every downstream value carries its data-state label from ingestion through to display |
| 9 | Signal lifecycle | Show a Signal's path: scan/strategy origin → grading → why-trade/why-not-trade → (optional) expiration | DS-SIG-001–004 | Exact field/state names from DS-SIG | PRS §9 (DS-SIG), Executive Product Plan | Illustrative | Describe the lifecycle as sequential stages producing an explained, gradeable candidate — never an executed trade |
| 10 | Strategy validation and promotion lifecycle | Show the strategy-promotion progression (Experimental → Backtest → Validation → Out-of-sample → Walk-forward → Shadow → Paper Auto-Trading → Limited Live → Approved Live) | TRADING_RULES.md "Strategy Promotion"; DS-PERF-004 | Exact nine stage names from `TRADING_RULES.md` | PRS §11/§19, Codex DS-002/DS-011 | Normative | List all nine stages in order; state that demotion can occur if performance deteriorates |
| 11 | Paper-to-live promotion path | Show the Gate-chain (Phase 7 → 8 → 12 → 13 → 14) and DS-EXE-007's live-trading prerequisite list | DS-RM-006 (DS-011); DS-EXE-007; DS-SCA-022 | Exact phase names and the eight DS-EXE-007 prerequisites | PRS §19, Executive Product Plan (roadmap section), Codex DS-011 | Normative | List the Gate-chain phases in order and the full prerequisite checklist as accessible text |
| 12 | Emergency Stop versus Emergency Flatten | Contrast the two controls: scope, authentication requirement, reachability | TRADING_RULES.md/SECURITY_RULES.md "Emergency Stop"/"Emergency Flatten"; DS-EXE-004/005; DS-SCA-016 | "Emergency Stop," "Emergency Flatten," "Strong Authentication Required" | PRS §11, Executive Product Plan (safety section), Codex DS-004/DS-008 | Normative | State each control's exact scope (block-new-orders-only vs. also-closes-positions) and authentication requirement |
| 13 | Mobile/desktop/backend relationship | Show both clients observing identical backend-authoritative state | DS-ARC-001/003; DS-MOB-002 | "Backend-authoritative state," "Client (Desktop)," "Client (Mobile, Planned Phase 9)" | PRS §6, Codex DS-004 | Normative (with an explicit Planned annotation on the mobile node) | State that mobile is Planned/Phase 9 and shown for architectural completeness, not current availability |
| 14 | Requirement-to-implementation traceability | Show the five-stage traceability chain: Requirement → Design/ADR → Source → Test → Release/Change | DS-002 §5.5; DS-QA-018; `docs/traceability/TRACEABILITY_MATRIX.csv` | Exact five stage names | PRS §21, Codex DS-009/traceability appendix | Normative | List the five stages in order; note that Source/Test/Release fields are frequently "Pending" at this stage of the project and that this is expected, not an error |
| 15 | Backlog promotion lifecycle | Show the eight-status DS-013 backlog taxonomy and the promotion process to a controlling authority | DS-BLG-002/003 (DS-013) | Exact eight statuses: Approved Future, Planned, Candidate, Deferred, Blocked, Research Needed, Rejected / Not Pursuing, Promoted | PRS §18/§19, Codex DS-013 | Normative | List all eight statuses; state explicitly that "Promoted" never means implemented, released, completed, or deployed |
| 16 | DS-013 versus DS-014 boundary | Show the DS-BLG-006/DS-IDG-005 boundary: DS-014 holds research-stage concepts, DS-013 holds productized candidates, each cross-referencing the other | DS-BLG-006; DS-IDG-005 | "Idea (DS-014)," "Backlog Item (DS-013)," "Promotion" | PRS §18, Codex DS-013/DS-014 | Conceptual | State that neither document restates the other's content as a second authority |
| 17 | Phase 0–14 roadmap | Show all fifteen `ROADMAP.md` phases with their sequencing category (Strict/Parallel/Optional-Deferred/Gate-chain) per DS-RM-015 | ROADMAP.md; DS-011 §6 (Phase Reference Table) | Exact phase names/numbers and sequencing-category labels | PRS §20, Executive Product Plan (roadmap section), Codex DS-011 | Normative | List all fifteen phases (0–14) with their sequencing category; state that phase inclusion alone never promotes a deliverable to Committed or Planned (DS-RM-012) |
| 18 | Threat boundaries | Show the seven trust boundaries from DS-SCA-023 (desktop↔backend, backend↔database, backend↔broker/provider adapters, Sage/model runtime↔deterministic services, local storage↔application process, update mechanism↔installed application, paper-trading↔live-trading boundary) | DS-SCA-023 | Exact seven boundary names | Codex DS-008 | Normative | List all seven boundaries; state that every boundary is enforced backend-side, never client-side-only |
| 19 | Flagship-publication relationship | Show how the Executive Product Plan, PRS, and Codex Complete Edition relate to each other and to the Markdown source | This document (§B) | "Markdown (authoritative source)," "Executive Product Plan," "PRS," "Codex Complete Edition" | This document, both other flagship documents' front matter | Conceptual | State that all three publication artifacts derive from the same Markdown source and that none is authoritative over another; the Markdown source is authoritative over all three |

Diagram source files (Mermaid or equivalent text-source per `docs/standards/DIAGRAM_STANDARD.md`) belong under `docs/assets/diagrams/`; this inventory does not itself create the diagram assets — it specifies what must eventually exist and what each must say.

## H. Generation and Publication Workflow

1. **Markdown source.** The approved, committed Markdown files under `docs/codex/`, `docs/publication/`, and `docs/requirements/` are the sole input.
2. **Structured extraction/transformation.** A (not-yet-built) extraction step parses each source document's headings, tables, requirement blocks, and metadata into a structured intermediate form, preserving exact text — no paraphrase introduced at this stage.
3. **Diagram assets.** Diagrams (§G) are produced as text-source (Mermaid or equivalent, per `docs/standards/DIAGRAM_STANDARD.md`) and rendered to embeddable images at generation time; rendered images are cached under `docs/assets/diagrams/` for reuse and diffability.
4. **DOCX generation.** The intermediate form is rendered into DOCX using the page/component/typography system defined in §D–§F.
5. **PDF generation.** Either generated directly from the intermediate form or exported from the DOCX generation step, depending on the tooling eventually selected — this architecture does not mandate a specific tool, only the visual/structural contract the output must satisfy.
6. **Link and TOC generation.** Cross-references (§E.4, §E.7) and the table of contents are generated from the source's own heading/ID structure, never hand-authored separately.
7. **Page-number and bookmark validation.** Automated check confirming every TOC entry resolves to the correct page and every cross-reference bookmark resolves to its target.
8. **Visual QA.** Human or automated review confirming no clipped table, no orphaned heading, correct font rendering, and correct color/contrast per §C.2.
9. **Source-to-publication consistency verification.** Automated diff-style check confirming every requirement ID, classification, and normative statement in the publication artifact matches its Markdown source exactly (§A.3/A.4).
10. **Artifact naming and versioning.** Publication artifacts are named `<DocumentID>_<PublicationVersion>_<GenerationDate>.<ext>` (e.g., `DSF-002_0.1.0_2026-08-01.pdf`), where PublicationVersion tracks the publication run and may differ from the source document's own Markdown version when a source is unchanged but regenerated for a formatting fix.
11. **Release folder layout.** Publication artifacts are organized under a dedicated release directory (not yet created; e.g., `docs/publication/releases/<PublicationVersion>/`), separate from the Markdown source tree, so source and generated artifacts are never intermingled.
12. **Checksum or manifest strategy.** Each publication run produces a manifest (§4 Definitions, "Publication manifest") recording, per artifact: filename, SHA-256 checksum, source document ID(s) and version(s), source baseline commit, generation timestamp, and publication version — so any distributed copy can be verified against the manifest of record.

This workflow is not yet implemented; no tooling selection is made here beyond the constraints above (text-source diagrams preferred, no proprietary font distribution, DOCX/PDF as the two target formats, PPTX deferred per §J).

## I. Quality Gates

A publication artifact is not releasable unless all of the following pass:

1. Every section required by the source document's own structure exists in the publication artifact (no silently dropped section).
2. Every internal and cross-document link resolves.
3. The table of contents and page numbers are correct (§H.7).
4. No table or diagram is clipped, truncated, or split in a way that loses information (§E.10, §E.8 page-break rules).
5. No orphan heading (a heading with no following content before the next heading, or a heading stranded alone at the bottom of a page with its content pushed to the next).
6. Headings and bookmarks are internally consistent (a heading's bookmark target matches its own text).
7. Every figure has a caption (§F "Figure Caption") and an accessibility description (§G's per-diagram requirement).
8. Every requirement ID, classification, and normative citation in the publication artifact matches its Markdown source exactly (§H.9) — no classification is changed, no requirement is created, removed, or reinterpreted by the publication process.
9. No generated text adds authority beyond what the Markdown source states — a publication artifact never states a classification, threshold, or commitment the source does not already state.
10. Fonts render correctly across the primary typeface and its fallback (§D.6) in the target generation environment.
11. Contrast and readability pass per §C.2 rule 6.
12. Metadata (document-control page, §E.2) is accurate and matches the manifest (§H.12).
13. The exported PDF is visually inspected by a human reviewer before release (automated checks alone are not sufficient for a release-blocking sign-off).
14. The source version is recorded in both the artifact's own document-control page and the publication manifest, and the two agree.

A Critical or High finding against any of these fourteen gates (per DS-QA-019's severity scale, applied here to publication artifacts) blocks release of that artifact until resolved, consistent with DS-DEV-009's Critical/High blocker-handling rule applied at the publication layer.

## J. Planned Outputs

### Executive Product Plan
- Markdown source (not yet authored)
- DOCX
- PDF
- Optional PPTX later (explicitly deferred; not part of this pass's scope)

### DarkSage Product Requirements Specification (DSF-002)
- Controlled Markdown (authored in this batch, v0.1.0)
- DOCX
- PDF

### Codex Complete Edition
- Fourteen individual DOCX files (one per DS-001–DS-014)
- Fourteen individual PDFs
- One master DOCX where technically practical (subject to tooling limits discovered during implementation)
- One master PDF
- Publication manifest (§H.12)
- Requirement index (drawn from each volume's own requirement IDs)
- ADR index (drawn from DS-012 §9's existing index)
- Traceability appendix (drawn from `docs/traceability/TRACEABILITY_MATRIX.csv`)

No DOCX or PDF artifact for any of the above is generated in this authoring pass. This section records the target output set so future generation work has an approved list to build against.

## Non-Goals

DSF-001 does not: redesign or reopen any approved Codex decision; create a new requirement-authority family (it governs presentation only, per §A); select a specific generation toolchain (§H states the workflow's stages and contract, not a product/vendor choice); commit to a delivery date for any planned output (§J); or generate any Word/PDF artifact in this pass.

## Dependencies

- [DS-001](../codex/Volume-01-Foundation/DS-001-Executive-Vision.md) §17 (terminology), §23 (governance relationship, Markdown-as-source-of-truth)
- [DS-002](../codex/Volume-02-Product/DS-002-SRS.md) §5.5 (traceability model)
- [DS-012](../codex/Volume-12-ADRs/DS-012-Architecture-Decision-Records.md) §7 (DS-ADR-010, conflict-resolution hierarchy)
- `docs/standards/BRAND_GUIDE.md`, `DIAGRAM_STANDARD.md`, `DOCUMENTATION_STANDARD.md`, `NAMING_AND_ID_STANDARD.md`, `STYLE_GUIDE.md`, `WRITING_GUIDE.md`
- `docs/CODEX_INDEX.md`, `docs/DOCUMENTATION_SUITE_README.md`
- [DSF-002 — DarkSage Product Requirements Specification](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md)

## Risks and Constraints

- **No generation tooling exists yet.** This document specifies the contract a future tool must satisfy; it does not itself validate that the contract is achievable in a specific tool until implementation begins. Treated as a known, non-blocking gap for this pass.
- **Diagram assets do not yet exist.** §G specifies what each of the nineteen diagrams must contain; none has been produced as a text-source asset yet. Recorded as planned work, not a defect in this document.
- **Font licensing not yet verified.** Aptos/Aptos Display and Consolas are named as preferred candidate typefaces per `docs/standards/STYLE_GUIDE.md`; their availability, licensing, and embedding rights for this repository's actual publication/export toolchain have not been verified as of this pass. §D.6's fallback stack (Calibri/Calibri Light, Courier New) applies wherever the preferred candidates, or their licensing/embedding rights, are unavailable or unconfirmed in a given generation environment. No proprietary font binary is committed to or distributed from this repository regardless of which typeface is ultimately used.
- **`DSF-NNN` prefix formally authorized.** `docs/standards/NAMING_AND_ID_STANDARD.md` now defines the `DSF-NNN` namespace (FLAG-H02 repair), consistent with DS-ADR-009's "routine, already-specified" category — this was a documentation-standard addition, not requiring a new ADR, since it creates no new decision authority (§A).

## Verification Approach

Document-level verification for this pass: unique-ID check against existing `DS-NNN`/`DS-<DOMAIN>-NNN`/`ADR-NNN`/`DSCP-NNN`/`DR-NNN` namespaces (no collision), cross-reference resolution against DS-001/DS-002/DS-012 and `docs/standards/*`, confirmation that no Word/PDF artifact was generated, and confirmation that no existing Codex volume was modified — recorded in `.ai-workflow/HANDOFF.md` for this task.

## References

- `docs/CODEX_INDEX.md`
- `docs/DOCUMENTATION_SUITE_README.md`
- `docs/standards/BRAND_GUIDE.md`, `DIAGRAM_STANDARD.md`, `DOCUMENTATION_STANDARD.md`, `NAMING_AND_ID_STANDARD.md`, `STYLE_GUIDE.md`, `WRITING_GUIDE.md`
- `docs/traceability/TRACEABILITY_MATRIX.csv`, `docs/traceability/README.md`
- [DS-001](../codex/Volume-01-Foundation/DS-001-Executive-Vision.md), [DS-011](../codex/Volume-11-Roadmap/DS-011-Development-Roadmap.md), [DS-012](../codex/Volume-12-ADRs/DS-012-Architecture-Decision-Records.md)
- [DSF-002 — DarkSage Product Requirements Specification](../requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md)

## Appendix A — Open Questions

1. **Generation tooling selection** — no specific DOCX/PDF generation toolchain has been chosen; §H states the required workflow stages and §I states the required quality gates independent of tooling choice, so this is not a blocker for approving this architecture, only for beginning implementation.
2. **RESOLVED in the FLAG-H02 targeted repair (v0.2.0).** `DSF-NNN` formal adoption into `docs/standards/NAMING_AND_ID_STANDARD.md` — the standards document now defines the namespace, its authority boundary, lifecycle, and uniqueness rule. Retained here for revision-history traceability, not as an open item.
3. **PPTX and additional Executive Product Plan formats** — explicitly deferred (§J); not evaluated in this pass.
4. **Font availability, licensing, and embedding-rights verification** — Aptos/Aptos Display/Consolas remain unverified preferred candidates (§D, Risks and Constraints); confirming actual rights/availability for the eventual export toolchain is required before generation begins, not resolved by this document.
5. **Governance-confirmation carryover** — the standing `.ai-workflow/BLOCKERS.md` items (`ROADMAP.md` phase boundaries as Codex release-scope authority; phase-mapping precision) are unaffected by this document and not re-litigated here.
