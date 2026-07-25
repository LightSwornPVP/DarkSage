# DarkSage Publication Tooling

Deterministic tooling supporting the DarkSage visual-publication batch (`DSF-001`–`DSF-004`, `docs/publication/DIAGRAM_REGISTER.md`, `docs/publication/PUBLICATION_MANIFEST.json`).

The validator/manifest/checksum scripts described below remain standard-library-only and dependency-free. A separate, opt-in document-generation and diagram-rendering toolchain (below) was added for the publication-output pass; it is isolated in its own repo-local venv/npm project and never touches the application's dependencies.

## Requirements

Python 3.9+, standard library only (`hashlib`, `subprocess`, `pathlib`, `json`, `re`, `argparse`, `dataclasses`, `urllib.parse`). No third-party packages, no network access, no paid services. See `requirements.txt` (intentionally empty for these four scripts).

## Document-Generation Tooling (`docgen/`)

Markdown → DOCX/PDF generation for the Executive Product Plan, PRS, and Codex volumes. Fully offline at runtime; no cloud conversion service, no pandoc dependency.

| Package | Version | License | Purpose | Installed into |
|---|---|---|---|---|
| `python-docx` | 1.1.2 | MIT | DOCX generation | `scripts/publication/.venv/` (isolated, repo-local, gitignored) |
| `reportlab` | 4.2.5 | BSD | PDF generation | `scripts/publication/.venv/` (isolated, repo-local, gitignored) |

This venv is **separate from the repository's application venv** (`.venv/` at repo root, used by the FastAPI backend) so publication tooling never pollutes or version-conflicts with application dependencies. Nothing here is installed system-wide.

Setup:

```
cd scripts/publication
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r docgen/requirements.txt
./.venv/Scripts/python.exe -m pip check   # dependency-conflict check
```

`pip check` was run after install on 2026-07-25: "No broken requirements found."

## Diagram-Rendering Tooling (Mermaid CLI)

`@mermaid-js/mermaid-cli` (`mmdc`) `11.4.2`, MIT license, declared as a `devDependency` in `scripts/publication/package.json` and installed only into `scripts/publication/node_modules/` (gitignored, never committed; `package.json`/`package-lock.json` are committed for reproducibility).

`mmdc` depends on Puppeteer to drive a Chromium-family browser for rendering. Puppeteer's own postinstall Chromium download did not run (blocked by the repo's npm allow-scripts policy) and was **not** manually triggered — no browser binary was downloaded. Instead, rendering points at an already-installed, non-project browser via the `PUPPETEER_EXECUTABLE_PATH` environment variable (Microsoft Edge, present by default on Windows). No new browser binary is installed by this tooling; on a machine without Chrome/Edge already present, rendering must be skipped or the operator must separately authorize a Chromium download.

`npm audit` after install on 2026-07-25: 0 vulnerabilities (266 dev/transitive packages).

Render invocation:

```
cd scripts/publication
PUPPETEER_EXECUTABLE_PATH="<path to an already-installed Chrome or Edge>" \
  ./node_modules/.bin/mmdc -i <source>.mmd -o <output>.svg
```

## Files

| File | Purpose |
|---|---|
| `_repo.py` | Shared helpers: repository-root resolution (relative to this file's own location, never a hard-coded personal path), `git rev-parse HEAD` lookup, SHA-256 hashing. Imported by every other script here. |
| `validate_publication.py` | Read-only validator. Runs every check listed below and exits nonzero on any FAIL-level finding. Never mutates a controlled source document. |
| `generate_manifest.py` | (Re)writes `docs/publication/PUBLICATION_MANIFEST.json` deterministically from the actual state of the repository — real Git HEAD, real source Version/Status, `generated: false`/null checksum for anything not actually on disk. |
| `record_baseline.py` | Prints (or writes) the actual current Git HEAD. Fails clearly, with a nonzero exit code, if Git metadata cannot be determined — never substitutes a hard-coded commit. |
| `checksum_artifacts.py` | Computes SHA-256 for one or more repository-relative paths. Reports `sha256: null` for any path that does not exist — never fabricates a value. |
| `tests/test_publication_tools.py` | Unit tests for the above (see Testing below). |

## Usage

```
python scripts/publication/validate_publication.py
python scripts/publication/generate_manifest.py
python scripts/publication/record_baseline.py
python scripts/publication/checksum_artifacts.py docs/publication/DIAGRAM_REGISTER.md
```

All paths accepted and printed by these tools are repository-relative. Run them from anywhere — the repository root is resolved from each script's own file location, not from the current working directory or any environment variable.

## Security: Path Containment

Every path a user supplies to these tools — `checksum_artifacts.py`'s positional arguments, `generate_manifest.py --output`, `record_baseline.py --output` — is resolved through `_repo.resolve_repo_path()`, which enforces containment before any read or write happens:

- **Absolute paths are rejected outright.** There is no "trusted absolute path" bypass anywhere in this tooling; every accepted input is repository-relative.
- **Any `..` segment in the supplied path is rejected**, regardless of whether it would actually resolve outside the repository — the pattern itself is refused, not only its effect.
- **The resolved target is checked against the repository root by path ancestry** (`Path.relative_to`), not by string-prefix matching, so `docs/publication` can never be confused with a sibling directory that merely starts with the same characters (e.g. `docs/publication-old`).
- **Symlink escapes are caught.** `Path.resolve()` follows symlinks before the containment check runs, so a symlink inside the repository that points outside it is still rejected.
- **Windows drive letters and case-insensitivity are handled**: the containment check has a case-normalized fallback so a differently-cased-but-otherwise-identical path is still recognized as contained, without weakening the ancestry check itself.
- **Violations fail closed**: `PathContainmentError` is raised, callers print a clear message to stderr and exit nonzero, and **no partial output is written** — a rejected `--output` path never creates a file, anywhere, and a rejected `checksum_artifacts.py` path is reported as `REJECTED`, never opened or hashed.

This was a genuine HIGH-severity gap in the prior revision of this tooling (the container check did not exist) and is now enforced for every read and write path in this directory.

## What `validate_publication.py` Checks

Required controlled metadata; Markdown heading structure (single H1, no skipped levels); relative-link resolution; `DSF-NNN` ID uniqueness; the Diagram Register's schema (exactly 19 rows, required columns including `Source Path`/`Rendered Path`); diagram source/rendered path truthfulness against what is actually on disk; that every `Figure N` placeholder in the Executive Product Plan cites a real Register row; that every authored diagram source carries a full-sentence accessibility description; `PUBLICATION_MANIFEST.json`'s JSON structure and required per-entry fields; that no manifest entry claims `generated: true` for a file that does not exist, or a non-null checksum/timestamp for a file marked `generated: false`; absence of absolute personal paths (`C:\Users\...`, `/home/...`, `/Users/...`); absence of obvious secret patterns; that any proprietary-font mention (Aptos/Consolas) is accompanied by a documented fallback stack; WCAG 2.2 AA contrast-ratio verification for DSF-003's repaired functional colors against Ivory White; **controlled-ID reference resolution** (every `DSF-NNN`/`DS-NNN`/`DS-<DOMAIN>-NNN`/`ADR-NNN` token in scoped publication Markdown must match a real heading in `docs/codex/**` or `docs/publication/**` — template placeholders are exempt because they never contain digits); **general Markdown-table structural validation** (see below) across every scoped Markdown file, not just the Diagram Register; and **Mermaid structural validation** (see below).

Exit code `0` means no FAIL-level finding. `WARN`-level findings are reported but do not fail the run — they flag things worth a human's attention (e.g. a possibly-stale status label) without blocking on them.

### Markdown-Table Validation Detail

A row immediately following a `|`-led header line is treated as an *attempted* delimiter row — including a malformed one — if every one of its cells consists only of decorative punctuation (`:`, `-`, and common wrong-character mistakes like `*`/`=`/`~`); this is deliberately broad so a malformed attempt is validated and FAILed rather than silently treated as "not a table" and skipped. Each cell is then validated strictly: only `---`, `:---`, `---:`, `:---:`-style cells (optional leading/trailing `:`, three or more `-` in between, nothing else) pass; too few hyphens or any other character fails, with the file, line, and specific cell reported. Delimiter/header column-count mismatches and body-row column-count mismatches (including one caused by an unescaped `|` inside a cell) are both reported the same way. Escaped pipes (`\|`) are always treated as literal characters, never a column separator.

### Mermaid Structural Validation — Honest Capability Boundary

`check_mermaid_sources()` is a **repository-local structural validator**, not a Mermaid parser and not a renderer. It checks:

- a supported diagram declaration exists;
- brackets/braces/quotes are balanced;
- **every edge's arrow token is checked against a fixed, exact-match allowlist** (`-->`, `---`, `-.->`, `<-->`, `<-.->`, `==>`) — any other arrow-shaped punctuation run (`~~>`, `--`, `<--`, `<==>`, etc.) is rejected with a file:line finding, not silently skipped;
- **node declarations are real**: a node counts as declared only via an explicit `ID["label"]`/`ID(label)`/`ID{label}` bracket/paren/brace declaration or a stateDiagram-v2 `ID: description` declaration — never merely by appearing as a bare edge endpoint, so an edge referencing a truly undeclared node is reported as a FAIL with file:line, and a `subgraph`/composite-`state` name is never mistaken for a node declaration;
- the `%% Figure N — Title` metadata comment is present and its number matches the file's actual Diagram Register row and filename;
- every diagram carries an accessibility description;
- the canonical-pipeline figure's stage sequence matches `docs/pipeline-stages.txt` exactly, in order;
- the Sage Advisory Boundary figure contains no Sage-to-Execution or Sage-to-Broker edge;
- **the DS-013/DS-014 Boundary figure's labels are checked semantically, not just its shape**: exactly one one-way `Idea --> Backlog` edge whose label identifies it as "Promotion" and states the approved-controlling-process requirement, and a separate bidirectional edge whose label identifies it as "Cross-reference" — swapped labels, a missing label on either edge, two edges both labeled "Promotion", a reverse (`Backlog --> Idea`) promotion, and a bidirectional edge mislabeled "Promotion" are all rejected.

**This is not equivalent to parser-backed or render-backed verification.** It remains a structural checker, not a full Mermaid grammar: it cannot catch every malformed construct a real Mermaid parser would reject, and it cannot confirm a diagram actually *renders* correctly. Full Mermaid rendering/parsing remains a later quality gate for whenever compatible tooling (e.g. Mermaid CLI) is available in the generation environment — this repository does not install one, per instruction.

## Testing

```
python -m unittest discover -s scripts/publication/tests -v
```

Tests use `tempfile`/`unittest.mock` to exercise real file-existence and Git-availability edge cases without depending on this specific machine's state, and never write into the actual repository tree.

## Design Notes

- **Deterministic output.** `generate_manifest.py` and `checksum_artifacts.py --json` sort keys and use fixed indentation so re-running against unchanged inputs produces byte-identical output.
- **Missing optional external programs are detected, not assumed.** No tool here shells out to a DOCX/PDF/diagram renderer; where the publication batch's diagram README notes that no Mermaid/Graphviz renderer was found, that was determined by attempting to invoke it and observing failure, not by assuming presence or absence.
- **Fail closed on ambiguity.** `record_baseline.py` and `generate_manifest.py` both raise a clear, nonzero-exit error rather than silently proceeding when Git is unavailable.
