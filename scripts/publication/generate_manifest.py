#!/usr/bin/env python3
"""Generate/update docs/publication/PUBLICATION_MANIFEST.json deterministically.

Reads the controlled publication sources actually present in the repository,
records the real Git HEAD as the baseline (via record_baseline.git_head),
and writes one manifest entry per source document and per planned artifact
named in DSF-001 §J's Planned Outputs list.

Rules enforced here (never violated regardless of caller):
- generated is always False, and generation_timestamp/checksum are always
  null, unless the artifact's planned_artifact_path actually exists on disk
  at write time (this tool has no DOCX/PDF generation capability, so in
  practice every artifact_type other than "markdown_source" is currently
  generated: false).
- source_version/source_status are read from each source file's own
  Document Control table — never invented.
- source_baseline is the real `git rev-parse HEAD` value.

Usage:
    python scripts/publication/generate_manifest.py
    python scripts/publication/generate_manifest.py --check   # exit 1 if output would differ from what's on disk
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from _repo import (
    REPO_ROOT,
    GitUnavailableError,
    PathContainmentError,
    eprint,
    git_head,
    repo_relative,
    resolve_repo_path,
    sha256_of_file,
)

MANIFEST_PATH = "docs/publication/PUBLICATION_MANIFEST.json"

# Controlled Markdown sources this manifest tracks. "document_id" is a
# DSF-NNN ID where one has been assigned, or a plain descriptive key for a
# production register that intentionally has no DSF-NNN ID (see
# DIAGRAM_REGISTER.md's own Document Control note).
SOURCES = [
    {"document_id": "DSF-001", "title": "DarkSage Publication Architecture", "source_path": "docs/publication/DARKSAGE_PUBLICATION_ARCHITECTURE.md"},
    {"document_id": "DSF-002", "title": "DarkSage Product Requirements Specification", "source_path": "docs/requirements/DARKSAGE_PRODUCT_REQUIREMENTS_SPECIFICATION.md"},
    {"document_id": "DSF-003", "title": "DarkSage Visual Design System", "source_path": "docs/publication/DARKSAGE_VISUAL_DESIGN_SYSTEM.md"},
    {"document_id": "DSF-004", "title": "DarkSage Executive Product Plan", "source_path": "docs/publication/DARKSAGE_EXECUTIVE_PRODUCT_PLAN.md"},
    {"document_id": "DIAGRAM-REGISTER", "title": "DarkSage Publication Diagram Register", "source_path": "docs/publication/DIAGRAM_REGISTER.md"},
]

# Planned (not-yet-generated) publication artifacts per DSF-001 §J. Paths are
# the intended release-folder location (DSF-001 §H.11); the actual generated
# filename will follow DSF-001 §H.10's <DocumentID>_<PublicationVersion>_<GenerationDate>.<ext>
# convention once a generation date is known — recorded in "notes", not guessed here.
PLANNED_ARTIFACTS = [
    {"document_id": "DSF-002", "title": "DarkSage Product Requirements Specification", "artifact_type": "docx", "planned_artifact_path": "docs/publication/releases/DSF-002.docx"},
    {"document_id": "DSF-002", "title": "DarkSage Product Requirements Specification", "artifact_type": "pdf", "planned_artifact_path": "docs/publication/releases/DSF-002.pdf"},
    {"document_id": "DSF-004", "title": "DarkSage Executive Product Plan", "artifact_type": "docx", "planned_artifact_path": "docs/publication/releases/DSF-004.docx"},
    {"document_id": "DSF-004", "title": "DarkSage Executive Product Plan", "artifact_type": "pdf", "planned_artifact_path": "docs/publication/releases/DSF-004.pdf"},
    {"document_id": "CODEX-MASTER", "title": "DarkSage Codex — Complete Edition (Master)", "artifact_type": "docx", "planned_artifact_path": "docs/publication/releases/DarkSage-Codex-Master.docx"},
    {"document_id": "CODEX-MASTER", "title": "DarkSage Codex — Complete Edition (Master)", "artifact_type": "pdf", "planned_artifact_path": "docs/publication/releases/DarkSage-Codex-Master.pdf"},
]

CODEX_VOLUMES = [
    ("DS-001", "Executive Vision & Product Foundation"),
    ("DS-002", "Product Requirements (SRS)"),
    ("DS-003", "Sage AI Assistant"),
    ("DS-004", "Technical Architecture"),
    ("DS-005", "Database and Data Design"),
    ("DS-006", "API and Integration Contracts"),
    ("DS-007", "UI/UX System"),
    ("DS-008", "Security Architecture"),
    ("DS-009", "Testing and Quality Assurance"),
    ("DS-010", "Development Standards"),
    ("DS-011", "Development Roadmap"),
    ("DS-012", "Architecture Decision Records"),
    ("DS-013", "Feature Backlog"),
    ("DS-014", "Idea Parking Lot"),
]
for _vol_id, _vol_title in CODEX_VOLUMES:
    for _artifact_type in ("docx", "pdf"):
        PLANNED_ARTIFACTS.append(
            {
                "document_id": _vol_id,
                "title": f"DarkSage Codex — {_vol_title} (Individual Edition)",
                "artifact_type": _artifact_type,
                "planned_artifact_path": f"docs/publication/releases/{_vol_id}.{_artifact_type}",
            }
        )

# Priority diagrams rendered for the publication-output pass (Part A). Each
# authored source (docs/publication/diagrams/source/*.mmd) yields two
# rendered artifacts under docs/publication/diagrams/rendered/: an
# authoritative SVG and a PNG fallback for DOCX embedding. Recorded here the
# same way as any other artifact — generated/checksum/timestamp are derived
# from whether the file actually exists on disk, never assumed.
DIAGRAM_RENDERS = [
    ("DIAGRAM-02", "Figure 2 — Public Authority Hierarchy", "docs/publication/diagrams/source/figure-02-authority-hierarchy.mmd", "figure-02-authority-hierarchy"),
    ("DIAGRAM-03", "Figure 3 — Canonical Trade Validation Pipeline", "docs/publication/diagrams/source/figure-03-trade-validation-pipeline.mmd", "figure-03-trade-validation-pipeline"),
    ("DIAGRAM-04", "Figure 4 — Backend-Authoritative Architecture", "docs/publication/diagrams/source/figure-04-backend-authoritative-architecture.mmd", "figure-04-backend-authoritative-architecture"),
    ("DIAGRAM-05", "Figure 5 — Sage Advisory Boundary", "docs/publication/diagrams/source/figure-05-sage-advisory-boundary.mmd", "figure-05-sage-advisory-boundary"),
    ("DIAGRAM-11", "Figure 11 — Paper-to-Live Promotion Path", "docs/publication/diagrams/source/figure-11-paper-to-live-promotion-path.mmd", "figure-11-paper-to-live-promotion-path"),
    ("DIAGRAM-16", "Figure 16 — DS-013 vs DS-014 Boundary", "docs/publication/diagrams/source/figure-16-ds013-vs-ds014-boundary.mmd", "figure-16-ds013-vs-ds014-boundary"),
    ("DIAGRAM-17", "Figure 17 — Phase 0-14 Roadmap", "docs/publication/diagrams/source/figure-17-phase-roadmap.mmd", "figure-17-phase-roadmap"),
    ("DIAGRAM-19", "Figure 19 — Flagship Document Relationship", "docs/publication/diagrams/source/figure-19-flagship-publication-relationship.mmd", "figure-19-flagship-publication-relationship"),
]

GENERATOR_VERSION_BY_TYPE = {
    "svg": "@mermaid-js/mermaid-cli 11.4.2 (scripts/publication/, Puppeteer pointed at local Edge via PUPPETEER_EXECUTABLE_PATH)",
    "png": "@mermaid-js/mermaid-cli 11.4.2 (scripts/publication/, Puppeteer pointed at local Edge via PUPPETEER_EXECUTABLE_PATH)",
    "docx": "scripts/publication/docgen (python-docx 1.1.2)",
    "pdf": "scripts/publication/docgen (reportlab 4.2.5)",
}


def iso_mtime(path: Path) -> str | None:
    """Return the file's actual filesystem mtime as UTC ISO-8601, or None if
    it does not exist. Never a fabricated or current-time value — sourced
    directly from the artifact's own modification time."""
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


FIELD_RE = re.compile(r"\|\s*(Version|Register Version|Status)\s*\|\s*([^\|]+?)\s*\|")


def read_source_metadata(rel_path: str) -> dict:
    """Extract Version/Status from a source's Document Control table by
    scanning its first ~40 lines. Returns None for a field that cannot be
    found — never invents a value."""
    abs_path = resolve_repo_path(rel_path)
    version = None
    status = None
    if abs_path.is_file():
        head_lines = abs_path.read_text(encoding="utf-8").splitlines()[:40]
        for line in head_lines:
            m = FIELD_RE.search(line)
            if not m:
                continue
            field, value = m.group(1), m.group(2).strip()
            if field in ("Version", "Register Version") and version is None:
                version = value
            elif field == "Status" and status is None:
                status = value
    return {
        "exists": abs_path.is_file(),
        "version": version,
        "status": status,
    }


def build_manifest() -> dict:
    baseline = git_head()

    entries = []

    for src in SOURCES:
        meta = read_source_metadata(src["source_path"])
        entries.append(
            {
                "document_id": src["document_id"],
                "title": src["title"],
                "source_path": src["source_path"],
                "source_version": meta["version"],
                "source_status": meta["status"],
                "source_baseline": baseline,
                "artifact_type": "markdown_source",
                "planned_artifact_path": src["source_path"],
                "generated": meta["exists"],
                "generation_timestamp": None,
                "checksum": sha256_of_file(resolve_repo_path(src["source_path"])) if meta["exists"] else None,
                "generator_version": None,
                "notes": "Markdown source is the authoritative document itself, not a generated artifact; 'generated' here means the source file exists, not that a DOCX/PDF was produced." if meta["exists"] else "Source file does not exist on disk.",
            }
        )

    source_by_id = {s["document_id"]: s for s in SOURCES}
    for planned in PLANNED_ARTIFACTS:
        artifact_abs = resolve_repo_path(planned["planned_artifact_path"])
        exists = artifact_abs.is_file()
        src = source_by_id.get(planned["document_id"])
        source_path = src["source_path"] if src else None
        meta = read_source_metadata(source_path) if source_path else {"version": None, "status": None}
        entries.append(
            {
                "document_id": planned["document_id"],
                "title": planned["title"],
                "source_path": source_path,
                "source_version": meta["version"],
                "source_status": meta["status"],
                "source_baseline": baseline,
                "artifact_type": planned["artifact_type"],
                "planned_artifact_path": planned["planned_artifact_path"],
                "generated": exists,
                "generation_timestamp": iso_mtime(artifact_abs) if exists else None,
                "checksum": sha256_of_file(artifact_abs) if exists else None,
                "generator_version": GENERATOR_VERSION_BY_TYPE.get(planned["artifact_type"]) if exists else None,
                "notes": (
                    "No DOCX/PDF generation tooling exists yet in this repository (DSF-001 §H is not yet implemented); "
                    "this entry records the planned output per DSF-001 §J. Actual generated filename will follow "
                    "DSF-001 §H.10's <DocumentID>_<PublicationVersion>_<GenerationDate>.<ext> convention once produced."
                    if not exists
                    else "Artifact file found on disk at write time."
                ),
            }
        )

    for doc_id, title, source_path, basename in DIAGRAM_RENDERS:
        for ext in ("svg", "png"):
            artifact_rel = f"docs/publication/diagrams/rendered/{basename}.{ext}"
            artifact_abs = resolve_repo_path(artifact_rel)
            exists = artifact_abs.is_file()
            entries.append(
                {
                    "document_id": doc_id,
                    "title": title,
                    "source_path": source_path,
                    "source_version": None,
                    "source_status": "Authored, rendered" if exists else "Authored (source only, not rendered)",
                    "source_baseline": baseline,
                    "artifact_type": ext,
                    "planned_artifact_path": artifact_rel,
                    "generated": exists,
                    "generation_timestamp": iso_mtime(artifact_abs) if exists else None,
                    "checksum": sha256_of_file(artifact_abs) if exists else None,
                    "generator_version": GENERATOR_VERSION_BY_TYPE.get(ext) if exists else None,
                    "notes": (
                        "Rendered from the authored Mermaid source via a rendering-only, comment-header-stripped "
                        "temporary copy (mmdc 11.4.2 fails to parse this file's leading %%-comment accessibility "
                        "block directly); the committed source file itself is unmodified by this rendering step. "
                        "See docs/publication/diagrams/README.md."
                        if exists
                        else "No renderer was available/authorized at authoring time; source exists, rendering pending."
                    ),
                }
            )

    return {
        "manifest_schema_version": "1.0.0",
        "generated_by": "scripts/publication/generate_manifest.py",
        "baseline_commit": baseline,
        "entries": entries,
    }


def render_manifest(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=MANIFEST_PATH, help="Repository-relative output path.")
    parser.add_argument("--check", action="store_true", help="Do not write; exit 1 if content would differ from the file on disk.")
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest()
    except GitUnavailableError as exc:
        eprint(f"ERROR: cannot generate manifest — {exc}")
        return 1

    text = render_manifest(manifest)
    try:
        out_path = resolve_repo_path(args.output)
    except PathContainmentError as exc:
        eprint(f"ERROR: refusing to write outside the repository — {exc}")
        eprint("No file was written.")
        return 1

    if args.check:
        if not out_path.is_file():
            eprint(f"CHECK FAILED: {args.output} does not exist.")
            return 1
        current = out_path.read_text(encoding="utf-8")
        if current != text:
            eprint(f"CHECK FAILED: {args.output} is stale relative to controlled sources / baseline.")
            return 1
        print(f"CHECK OK: {args.output} matches current sources and baseline.")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Manifest written: {repo_relative(out_path)} ({len(manifest['entries'])} entries, baseline {manifest['baseline_commit']})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
