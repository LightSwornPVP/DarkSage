# DarkSage Publication Diagrams

Flagship-publication-batch diagram source staging area. Indexed by [DIAGRAM_REGISTER.md](../DIAGRAM_REGISTER.md); governed by [DSF-001 §G/§H.3](../DARKSAGE_PUBLICATION_ARCHITECTURE.md) and [DSF-003 §9](../DARKSAGE_VISUAL_DESIGN_SYSTEM.md).

## Location note (open coordination point, non-blocking)

DSF-001 §H.3 and §316 name `docs/assets/diagrams/` as the repository's general diagram-source and rendered-image-cache location. This directory, `docs/publication/diagrams/`, is this visual-publication batch's own staging location for the eight HIGH4 priority diagram sources, created because the current repair task explicitly directed sources here. The two locations are not yet reconciled — a future pass should either mirror/move these sources into `docs/assets/diagrams/` to match DSF-001 exactly, or amend DSF-001 §H.3 to name this location, whichever Keeper/Codex decide. Until then: **this directory holds real, existing source files; `docs/assets/diagrams/` remains DSF-001's stated authoritative location for the general diagram system.** Neither location's content overrides the controlling Codex text a diagram illustrates — see Authority Rules below.

## Source Format

- Preferred: Mermaid (`.mmd`), per `docs/standards/DIAGRAM_STANDARD.md`.
- Where Mermaid is unsuitable for a given diagram's structure: Graphviz (`.dot`).
- Plain text, diffable in Git — no binary diagram-editor project files.
- No proprietary icon libraries or external image dependencies; diagrams use text labels and the palette below only.

## Naming Convention

`figure-NN-<slug>.mmd` (or `.dot`), where `NN` is the two-digit `#` from `DIAGRAM_REGISTER.md` and `<slug>` is a kebab-case short form of the diagram's title — matching the DSF-001 §F "Figure N — Title" caption convention and `docs/standards/NAMING_AND_ID_STANDARD.md` §File Naming.

## Rendering Expectations

- Rendering to SVG/PNG happens via `@mermaid-js/mermaid-cli` (`mmdc`) 11.4.2, installed as a repo-local npm devDependency in `scripts/publication/` (see `scripts/publication/README.md`, "Diagram-Rendering Tooling") — never system-wide, and no new browser binary was downloaded (Puppeteer is pointed at the machine's existing Microsoft Edge via `PUPPETEER_EXECUTABLE_PATH`).
- `mmdc` 11.4.2 cannot parse a source file whose very first line is a `%%` Mermaid comment (a real tooling limitation, confirmed by isolating it against a minimal reproduction). Rendering therefore runs against a temporary, non-committed copy of each source with its leading `%%`-comment accessibility header stripped; **the committed source file under `source/` is never modified by this step** — only `figure-11-paper-to-live-promotion-path.mmd` needed an actual content fix (an invalid chained `stateDiagram-v2` transition, split into separate transition lines with identical meaning; see Diagram Register v0.4.0).
- All eight priority diagrams (Figures 2, 3, 4, 5, 11, 16, 17, 19) are rendered as of this pass; the remaining eleven diagrams in the 19-diagram inventory remain Not Yet Authored, so nothing renders them yet.
- Every rendered asset's XML (SVG) validity and existence is checked by `scripts/publication/validate_publication.py`, and the Diagram Register's Status column reflects the real file's existence — never a fabricated or assumed-generated file path.

## Accessibility Rules

- Every source file carries a full-sentence accessibility description in its own header comment block (`%%` for Mermaid, `//` or comment nodes for Graphviz) — never a one-word alt tag, per DSF-003 §9.8.
- The accessibility description states the diagram's meaning in prose sufficient to stand in for the image entirely (exact stage/tier/phase order where order is the diagram's meaning, exact boundary statements where a boundary is the diagram's meaning).
- Color is never the sole carrier of meaning in a rendered diagram: every semantically-colored node/edge also carries a text label, matching DSF-001 §C.2 rule 3 and DSF-003 §2's accessibility rules.

## Authority Rules

- A diagram source file never overrides, reinterprets, or restates as a second authority any controlling Codex volume, ADR, or root governance document text it illustrates. Where a diagram and its cited source text differ, the source text governs and the diagram is a defect to be corrected (same rule as DSF-001 §A.2.4 applied to diagrams specifically).
- A diagram file does not, by existing, promote a Future/Exploratory or Planned item to Committed, or a DS-013/DS-014 item to product-requirement status — classification labels shown in a diagram (e.g., "Planned Phase 9," "Gate-chain") are reproduced from their controlling source, never invented here.
- No diagram shows an execution or data path that does not exist in the controlling architecture — in particular, no diagram may show Sage calling the Execution Engine or Broker Adapter directly (DSF-001 §G row 5), and no diagram may show a client (desktop or mobile) holding authoritative trading state independent of the backend (DSF-001 §G row 4).

## Styling

Diagrams use the DSF-001/DSF-003 palette where Mermaid/Graphviz syntax supports fill/stroke colors: Obsidian Black (`#0B0B0D`), Charcoal Gray (`#17181C`), Steel Gray (`#2A2D33`), Soft Gray (`#A7ABB3`), Ivory White (`#F4F2EC`), Sage Gold (`#C8A45D`), Highlight Gold (`#E0BE72`, reserved use only). Functional colors used for semantic state only (never decoratively), per DSF-003 §2.2/§2.3 as repaired: Signal Green (Text/Icon) `#1E6E43`, Risk Red `#A33A3A`, Warning Amber (Text/Icon) `#8A6013`, Info Blue `#3B6EA5`.

## How to Validate

Run `python scripts/publication/validate_publication.py` from the repository root. It checks, among other things: every `Planned Source File`/`Source Path` entry in `DIAGRAM_REGISTER.md` that claims a real file actually exists on disk; every `Rendered Path` entry claiming a rendered artifact actually exists on disk (and is not silently assumed); and that no diagram source or register entry fabricates a checksum or generation timestamp for a file that was not actually produced.

## Current Status

Eight priority diagram sources exist under `source/` (Figures 2, 3, 4, 5, 11, 16, 17, 19 — see `DIAGRAM_REGISTER.md`) and are now rendered to SVG + PNG under `rendered/`. The remaining eleven diagrams in the 19-diagram inventory remain **Not Yet Authored**.
