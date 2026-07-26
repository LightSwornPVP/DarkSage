#!/usr/bin/env python3
"""Validate the DarkSage publication batch (docs/publication/**,
docs/requirements/**, docs/publication/diagrams/**) without mutating any
controlled source document.

Standard library only. No network access. Exits 0 only if no FAIL-level
finding was produced; WARN-level findings are reported but do not fail the
run. Every check is read-only.

Usage:
    python scripts/publication/validate_publication.py
    python scripts/publication/validate_publication.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from _repo import REPO_ROOT, repo_relative, resolve_repo_path, sha256_of_file

PUBLICATION_DIRS = [
    "docs/publication",
    "docs/requirements",
]

TEMPLATE_DIR_PREFIXES = ("docs/publication/templates",)

DIAGRAM_REGISTER_PATH = "docs/publication/DIAGRAM_REGISTER.md"
MANIFEST_PATH = "docs/publication/PUBLICATION_MANIFEST.json"
DIAGRAM_SOURCE_DIR = "docs/publication/diagrams/source"


@dataclass
class Finding:
    severity: str  # "FAIL" | "WARN" | "OK"
    check: str
    message: str


@dataclass
class Report:
    findings: list = field(default_factory=list)

    def add(self, severity: str, check: str, message: str) -> None:
        self.findings.append(Finding(severity, check, message))

    def ok(self, check: str, message: str) -> None:
        self.add("OK", check, message)

    def fail(self, check: str, message: str) -> None:
        self.add("FAIL", check, message)

    def warn(self, check: str, message: str) -> None:
        self.add("WARN", check, message)

    @property
    def has_failures(self) -> bool:
        return any(f.severity == "FAIL" for f in self.findings)


def _iter_markdown_files(rel_dirs: list[str], exclude_prefixes: tuple = ()) -> list[Path]:
    out = []
    for rel_dir in rel_dirs:
        base = resolve_repo_path(rel_dir)
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = repo_relative(p)
            if any(rel.startswith(pref) for pref in exclude_prefixes):
                continue
            out.append(p)
    return out


DOC_CONTROL_REQUIRED_FIELDS = ["Document ID", "Title", "Version", "Status", "Owner", "Classification"]
DOC_CONTROL_FIELD_RE = re.compile(r"^\|\s*([A-Za-z ]+?)\s*\|\s*(.*?)\s*\|\s*$")


def check_controlled_metadata(report: Report) -> None:
    check = "required-controlled-metadata"
    files = _iter_markdown_files(PUBLICATION_DIRS, TEMPLATE_DIR_PREFIXES)
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if "Document ID" not in text[:2000] and "Register For" not in text[:2000]:
            # Not a controlled document (e.g. a README) — skip.
            continue
        head = text.splitlines()[:30]
        fields_present = set()
        for line in head:
            m = DOC_CONTROL_FIELD_RE.match(line)
            if m:
                fields_present.add(m.group(1).strip())
        missing = [fld for fld in DOC_CONTROL_REQUIRED_FIELDS if fld not in fields_present]
        # DIAGRAM_REGISTER.md intentionally uses "Register For"/no Owner-as-DSF-doc convention differences are tolerated.
        if repo_relative(f) == DIAGRAM_REGISTER_PATH:
            continue
        if missing:
            report.fail(check, f"{repo_relative(f)}: missing Document Control field(s): {', '.join(missing)}")
        else:
            report.ok(check, f"{repo_relative(f)}: all required Document Control fields present")


HEADING_RE = re.compile(r"^(#{1,6})\s+\S")


def check_markdown_headings(report: Report) -> None:
    check = "markdown-heading-structure"
    files = _iter_markdown_files(PUBLICATION_DIRS)
    for f in files:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        h1_count = 0
        prev_level = 0
        skip_found = False
        in_fence = False
        for line in lines:
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = HEADING_RE.match(line)
            if not m:
                continue
            level = len(m.group(1))
            if level == 1:
                h1_count += 1
            if prev_level and level > prev_level + 1:
                skip_found = True
            prev_level = level
        rel = repo_relative(f)
        if h1_count == 0 and rel.endswith("README.md"):
            continue  # READMEs are not required to carry a single H1 title
        if rel.startswith("docs/publication/templates/") and not rel.endswith("README.md"):
            continue  # page-fragment templates intentionally start below H1 (docs/publication/templates/README.md documents this)
        if h1_count != 1:
            report.warn(check, f"{rel}: expected exactly one H1, found {h1_count}")
        if skip_found:
            report.warn(check, f"{rel}: a heading level skip was detected (e.g. H2 -> H4)")
        if h1_count == 1 and not skip_found:
            report.ok(check, f"{rel}: heading structure OK")


LINK_RE = re.compile(r"\]\(([^)]+)\)")


def check_relative_links(report: Report) -> None:
    check = "relative-link-resolution"
    files = _iter_markdown_files(PUBLICATION_DIRS)
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target or target.startswith("{{"):
                continue
            parsed = urlparse(target)
            if parsed.scheme in ("http", "https", "mailto"):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (f.parent / path_part).resolve()
            if resolved.is_file():
                report.ok(check, f"{repo_relative(f)}: link '{target}' resolves")
            else:
                report.fail(check, f"{repo_relative(f)}: broken relative link '{target}'")


DSF_ID_RE = re.compile(r"\bDSF-(\d{3})\b")


def check_dsf_id_uniqueness(report: Report) -> None:
    check = "dsf-id-uniqueness"
    files = _iter_markdown_files(["docs"])
    id_to_files: dict[str, set[str]] = {}
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if not lines:
            continue
        m = re.match(r"^#\s+(DSF-\d{3})\b", lines[0])
        if m:
            doc_id = m.group(1)
            id_to_files.setdefault(doc_id, set()).add(repo_relative(f))
    for doc_id, owners in sorted(id_to_files.items()):
        if len(owners) > 1:
            report.fail(check, f"{doc_id} is declared as the H1 document ID in multiple files: {sorted(owners)}")
        else:
            report.ok(check, f"{doc_id} unique -> {sorted(owners)[0]}")


def check_diagram_register_schema(report: Report):
    check = "diagram-register-schema"
    path = resolve_repo_path(DIAGRAM_REGISTER_PATH)
    if not path.is_file():
        report.fail(check, f"{DIAGRAM_REGISTER_PATH} does not exist")
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("| # | Diagram |"):
            header_idx = i
            break
    if header_idx is None:
        report.fail(check, "could not find the Register table header row")
        return None
    header_cols = [c.strip() for c in lines[header_idx].strip("|").split("|")]
    expected_min_cols = ["#", "Diagram", "Purpose", "Source Volumes", "Authoritative Labels", "Placement(s)", "Type", "Accessibility Text Requirement"]
    missing_cols = [c for c in expected_min_cols if c not in header_cols]
    if missing_cols:
        report.fail(check, f"Register table missing expected column(s): {missing_cols}")
    if "Source Path" not in header_cols or "Rendered Path" not in header_cols:
        report.fail(check, "Register table missing 'Source Path'/'Rendered Path' columns (HIGH5 requirement)")

    row_nums = []
    rows = {}
    for line in lines[header_idx + 2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0].isdigit():
            continue
        num = int(cells[0])
        row_nums.append(num)
        rows[num] = dict(zip(header_cols, cells))

    expected = list(range(1, 20))
    if row_nums != expected:
        report.fail(check, f"Register does not contain exactly rows 1-19 in order (found: {row_nums})")
    else:
        report.ok(check, "Register contains exactly 19 rows (1-19), in order")

    return rows


def check_diagram_path_truthfulness(report: Report, rows) -> None:
    check = "diagram-path-truthfulness"
    if not rows:
        report.warn(check, "skipped — Register rows unavailable (schema check failed)")
        return
    path_re = re.compile(r"`([^`]+\.(?:mmd|dot|svg|png|pdf))`")
    for num, row in rows.items():
        status = row.get("Status", "")
        source_cell = row.get("Source Path", "")
        rendered_cell = row.get("Rendered Path", "")

        src_match = path_re.search(source_cell)
        if src_match:
            src_path = resolve_repo_path(src_match.group(1))
            exists = src_path.is_file()
            authored = status.startswith("Authored") or status == "Rendered"
            if authored and not exists:
                report.fail(check, f"Figure {num}: Status says '{status}' but source path does not exist on disk: {src_match.group(1)}")
            elif not authored and exists:
                report.warn(check, f"Figure {num}: Status says '{status}' but a source file actually exists at {src_match.group(1)} — status is stale")
            else:
                report.ok(check, f"Figure {num}: source path/status consistent (exists={exists}, status='{status}')")

        rendered_match = path_re.search(rendered_cell)
        if rendered_match:
            rendered_path = resolve_repo_path(rendered_match.group(1))
            if not rendered_path.is_file():
                report.fail(check, f"Figure {num}: Rendered Path cell names a file that does not exist: {rendered_match.group(1)}")
            else:
                report.ok(check, f"Figure {num}: rendered artifact exists as claimed")
        else:
            if "Pending" not in rendered_cell and "Not Yet Rendered" not in rendered_cell:
                report.warn(check, f"Figure {num}: Rendered Path cell '{rendered_cell}' is neither a real path nor a recognized honest placeholder")


FIGURE_PLACEHOLDER_RE = re.compile(r"Figure\s+(\d{1,2})\s*[—-]")


def check_figure_placeholders(report: Report) -> None:
    check = "figure-placeholders"
    epp_path = resolve_repo_path("docs/publication/DARKSAGE_EXECUTIVE_PRODUCT_PLAN.md")
    if not epp_path.is_file():
        report.warn(check, "Executive Product Plan not found — skipping figure-placeholder check")
        return
    text = epp_path.read_text(encoding="utf-8")
    found = sorted(set(int(n) for n in FIGURE_PLACEHOLDER_RE.findall(text)))
    for n in found:
        if 1 <= n <= 19:
            report.ok(check, f"Figure {n} placeholder references a valid Diagram Register row")
        else:
            report.fail(check, f"Figure {n} placeholder references a row outside the Register's 1-19 range")
    if not found:
        report.warn(check, "no 'Figure N —' placeholders found in the Executive Product Plan")


def check_accessibility_descriptions(report: Report) -> None:
    check = "accessibility-descriptions"
    src_dir = resolve_repo_path(DIAGRAM_SOURCE_DIR)
    if not src_dir.is_dir():
        report.warn(check, f"{DIAGRAM_SOURCE_DIR} does not exist — nothing to check")
        return
    for f in sorted(src_dir.glob("*.mmd")) + sorted(src_dir.glob("*.dot")):
        text = f.read_text(encoding="utf-8")
        if "Accessibility description" not in text:
            report.fail(check, f"{repo_relative(f)}: no 'Accessibility description' comment block found")
            continue
        idx = text.index("Accessibility description")
        snippet = text[idx: idx + 800]
        words = re.findall(r"\w+", snippet)
        if len(words) < 25:
            report.warn(check, f"{repo_relative(f)}: accessibility description looks too short ({len(words)} words)")
        else:
            report.ok(check, f"{repo_relative(f)}: accessibility description present ({len(words)}+ words)")


def check_manifest_json(report: Report):
    check = "manifest-json-parse"
    path = resolve_repo_path(MANIFEST_PATH)
    if not path.is_file():
        report.fail(check, f"{MANIFEST_PATH} does not exist")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.fail(check, f"{MANIFEST_PATH} is not valid JSON: {exc}")
        return None
    report.ok(check, f"{MANIFEST_PATH} parses as valid JSON")

    required_top = ["manifest_schema_version", "baseline_commit", "entries"]
    missing_top = [k for k in required_top if k not in data]
    if missing_top:
        report.fail(check, f"manifest missing top-level key(s): {missing_top}")
    entries = data.get("entries", [])
    if not isinstance(entries, list) or not entries:
        report.fail(check, "manifest 'entries' is missing or empty")
    required_entry_fields = [
        "document_id", "title", "source_path", "source_version", "source_status",
        "source_baseline", "artifact_type", "planned_artifact_path", "generated",
        "generation_timestamp", "checksum", "generator_version", "notes",
    ]
    for i, entry in enumerate(entries):
        missing = [k for k in required_entry_fields if k not in entry]
        if missing:
            report.fail(check, f"manifest entry #{i} ({entry.get('document_id')}) missing field(s): {missing}")
    return data


def check_manifest_generated_truthfulness(report: Report, manifest) -> None:
    check = "manifest-generated-truthfulness"
    if not manifest:
        report.warn(check, "skipped — manifest unavailable")
        return
    for entry in manifest.get("entries", []):
        doc_id = entry.get("document_id")
        generated = entry.get("generated")
        planned_path = entry.get("planned_artifact_path")
        checksum = entry.get("checksum")
        timestamp = entry.get("generation_timestamp")

        artifact_exists = False
        if planned_path:
            artifact_exists = resolve_repo_path(planned_path).is_file()

        if generated and not artifact_exists:
            report.fail(check, f"{doc_id}: marked generated=true but '{planned_path}' does not exist on disk")
            continue
        if not generated and artifact_exists and entry.get("artifact_type") != "markdown_source":
            report.warn(check, f"{doc_id}: marked generated=false but '{planned_path}' actually exists — manifest is stale, regenerate it")
        if not generated and (checksum is not None or timestamp is not None):
            report.fail(check, f"{doc_id}: generated=false but checksum/timestamp is non-null (fabricated-looking value)")
        if generated and artifact_exists:
            actual = sha256_of_file(resolve_repo_path(planned_path))
            if checksum != actual:
                report.fail(check, f"{doc_id}: recorded checksum does not match the actual file's SHA-256")
            else:
                report.ok(check, f"{doc_id}: generated artifact's checksum verified")
        if not generated and not artifact_exists:
            report.ok(check, f"{doc_id}: honestly marked not generated, no file present")


ABS_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\Users\\[^\s`\"')]+", re.IGNORECASE),
    re.compile(r"/home/[A-Za-z0-9_.\-]+/[^\s`\"')]+"),
    re.compile(r"/Users/[A-Za-z0-9_.\-]+/[^\s`\"')]+"),
]


_VENDORED_DIR_NAMES = {".venv", "node_modules", "__pycache__"}


def _not_vendored(path: Path) -> bool:
    return _VENDORED_DIR_NAMES.isdisjoint(path.parts)


def check_no_absolute_personal_paths(report: Report) -> None:
    check = "no-absolute-personal-paths"
    files = _iter_markdown_files(PUBLICATION_DIRS) + [
        p for p in resolve_repo_path("scripts/publication").rglob("*.py") if _not_vendored(p)
    ]
    hit = False
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        for pat in ABS_PATH_PATTERNS:
            m = pat.search(text)
            if m:
                report.fail(check, f"{repo_relative(f)}: possible absolute personal path: {m.group(0)[:60]}")
                hit = True
    if not hit:
        report.ok(check, "no absolute personal paths found in docs/publication/** or scripts/publication/**")


SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"),
    re.compile(r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]{4,}['\"]"),
    re.compile(r"(?i)\bsecret\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
]


def check_no_secrets(report: Report) -> None:
    check = "no-obvious-secrets"
    files = (
        _iter_markdown_files(PUBLICATION_DIRS)
        + [p for p in resolve_repo_path("scripts/publication").rglob("*.py") if _not_vendored(p)]
        + list(resolve_repo_path("docs/publication/diagrams").rglob("*.mmd"))
    )
    hit = False
    for f in files:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                report.fail(check, f"{repo_relative(f)}: possible secret matched pattern {pat.pattern[:30]}...")
                hit = True
    if not hit:
        report.ok(check, "no obvious secret patterns found")


def check_no_unsupported_proprietary_font(report: Report) -> None:
    check = "no-unsupported-proprietary-font-requirement"
    files = _iter_markdown_files(PUBLICATION_DIRS)
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        mentions_proprietary = bool(re.search(r"\b(Aptos|Consolas)\b", text))
        if mentions_proprietary and "fallback" not in text.lower():
            report.fail(check, f"{repo_relative(f)}: mentions a proprietary font (Aptos/Consolas) with no fallback stack documented")
        elif mentions_proprietary:
            report.ok(check, f"{repo_relative(f)}: proprietary font mention is accompanied by a fallback stack")


def _srgb_to_linear(c: int) -> float:
    cs = c / 255.0
    return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    la, lb = _relative_luminance(hex_a), _relative_luminance(hex_b)
    lighter, darker = (la, lb) if la >= lb else (lb, la)
    return (lighter + 0.05) / (darker + 0.05)


IVORY_WHITE = "#F4F2EC"


def check_contrast_ratios(report: Report) -> None:
    check = "contrast-ratio-verification"
    # These must match docs/publication/DARKSAGE_VISUAL_DESIGN_SYSTEM.md §2.2/§2.3 exactly.
    functional_colors = {
        "Signal Green (Text/Icon)": "#1E6E43",
        "Risk Red": "#A33A3A",
        "Warning Amber (Text/Icon)": "#8A6013",
        "Info Blue": "#3B6EA5",
    }
    for name, hex_color in functional_colors.items():
        ratio = contrast_ratio(hex_color, IVORY_WHITE)
        if ratio < 3.0:
            report.fail(check, f"{name} ({hex_color}) vs Ivory White: {ratio:.2f}:1 — below even the 3:1 large-text/graphical minimum")
        elif ratio < 4.5:
            report.fail(check, f"{name} ({hex_color}) vs Ivory White: {ratio:.2f}:1 — below the 4.5:1 normal-text minimum")
        else:
            report.ok(check, f"{name} ({hex_color}) vs Ivory White: {ratio:.2f}:1 — meets WCAG 2.2 AA (>=4.5:1 normal text)")


# ---------------------------------------------------------------------------
# HIGH4-A: Controlled-ID reference validation
# ---------------------------------------------------------------------------


# A requirement domain segment is one or more hyphen-joined uppercase groups
# (e.g. "JRN", or the compound "API-JRN") — `(?:[A-Z]{2,8}-)+` — so both a
# plain domain ID (DS-JRN-001) and a compound API ID (DS-API-JRN-001,
# DS-API-TIP-001) are recognized as the same controlled-ID family. Without
# the compound form, every DS-API-<DOMAIN>-NNN identifier defined in DS-006
# was silently invisible to both reference-resolution and definition
# counting, undercounting the true controlled-ID inventory.
CONTROLLED_ID_RE = re.compile(r"\b(DSF-\d{3}|ADR-\d{3}|DS-\d{3}|DS-(?:[A-Z]{2,8}-)+\d{3})\b")
VOLUME_H1_RE = re.compile(r"^#\s+(DS-\d{3})\b")
DOMAIN_REQ_HEADING_RE = re.compile(r"^#{2,4}\s+(DS-(?:[A-Z]{2,8}-)+\d{3})\b")
ADR_H1_RE = re.compile(r"^#\s+(ADR-\d{3})\b")
DSF_H1_RE = re.compile(r"^#\s+(DSF-\d{3})\b")


def collect_controlled_definitions_with_locations() -> dict:
    """Collect every controlled ID (DS-NNN volume, DS-<DOMAIN>-NNN
    requirement — including the compound DS-API-<DOMAIN>-NNN form used by
    DS-006's API contracts — ADR-NNN, DSF-NNN) actually *defined* by a
    heading in the committed Codex or the publication batch, mapped to every
    file that defines it. Never invented — only IDs that exist as a real
    heading count as defined. Returning every defining file (not just a
    deduplicated set of IDs) lets callers detect an ID defined in more than
    one place instead of silently collapsing the duplicate into a single
    entry and inflating the apparent inventory."""
    id_to_files: dict[str, set] = {}
    codex_dir = resolve_repo_path("docs/codex")
    if codex_dir.is_dir():
        for f in codex_dir.rglob("*.md"):
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                for rx in (VOLUME_H1_RE, DOMAIN_REQ_HEADING_RE, ADR_H1_RE):
                    m = rx.match(line)
                    if m:
                        id_to_files.setdefault(m.group(1), set()).add(repo_relative(f))
    for base in PUBLICATION_DIRS:
        d = resolve_repo_path(base)
        if not d.is_dir():
            continue
        for f in d.rglob("*.md"):
            if repo_relative(f).startswith(TEMPLATE_DIR_PREFIXES):
                continue
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            if lines:
                m = DSF_H1_RE.match(lines[0])
                if m:
                    id_to_files.setdefault(m.group(1), set()).add(repo_relative(f))
    return id_to_files


def collect_controlled_definitions() -> set:
    """Convenience wrapper: the set of unique controlled IDs, discarding the
    per-file location detail. Use collect_controlled_definitions_with_locations()
    directly when duplicate-location detection matters."""
    return set(collect_controlled_definitions_with_locations().keys())


# A requirement domain segment's grammar, standalone, for validating a
# candidate token that was found via the broader ID_CANDIDATE_HEADING_RE
# below — never used to *find* candidates, only to judge ones already found.
STRICT_ID_FULLMATCH_RES = [
    re.compile(r"^DSF-\d{3}$"),
    re.compile(r"^ADR-\d{3}$"),
    re.compile(r"^DS-\d{3}$"),
    re.compile(r"^DS-(?:[A-Z]{2,8}-)+\d{3}$"),
]

# Deliberately broad "this heading token looks like an attempted controlled
# ID" detector — anything starting with DS-/ADR-/DSF-, optionally followed by
# domain segment(s), ending in a segment that *starts with a digit* (a real
# ID's final NNN segment always does). This last-segment-starts-with-digit
# requirement is what distinguishes a numbered ID attempt (DS-JRN-001,
# DS-jrn-01, ADR-12 — all candidates, some malformed) from a bare domain/
# family H1 title like "DS-JRN — Journal & Review Intelligence", which
# legitimately has no trailing number and must not be flagged. Malformed
# attempts (lowercase, wrong digit count) are still caught; used only to
# *find* candidates so they can be checked against STRICT_ID_FULLMATCH_RES,
# never used by itself to decide a token is a valid controlled ID.
ID_CANDIDATE_HEADING_RE = re.compile(r"^#{1,6}\s+((?:DS|ADR|DSF)(?:-[A-Za-z0-9]+)*-[0-9][A-Za-z0-9]*)\b")


def check_controlled_id_inventory(report: Report) -> None:
    """HIGH4-A extension: the dynamically-derived controlled-ID inventory
    itself — duplicate definitions and malformed near-miss ID headings —
    which check_controlled_id_references (reference *resolution*) does not
    cover on its own."""
    check = "controlled-id-inventory"
    id_to_files = collect_controlled_definitions_with_locations()

    dup_count = 0
    for doc_id, files in sorted(id_to_files.items()):
        if len(files) > 1:
            report.fail(check, f"{doc_id} is defined as a controlled-ID heading in more than one file: {sorted(files)}")
            dup_count += 1
    if dup_count == 0:
        report.ok(check, f"no duplicate controlled-ID definitions found across {len(id_to_files)} unique ID(s)")

    files = []
    codex_dir = resolve_repo_path("docs/codex")
    if codex_dir.is_dir():
        files.extend(codex_dir.rglob("*.md"))
    for base in PUBLICATION_DIRS:
        d = resolve_repo_path(base)
        if d.is_dir():
            files.extend(p for p in d.rglob("*.md") if not repo_relative(p).startswith(TEMPLATE_DIR_PREFIXES))

    malformed = 0
    for f in files:
        for lineno, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            m = ID_CANDIDATE_HEADING_RE.match(line)
            if not m:
                continue
            token = m.group(1)
            if not any(rx.match(token) for rx in STRICT_ID_FULLMATCH_RES):
                report.fail(check, f"{repo_relative(f)}:{lineno}: heading token '{token}' looks like an attempted controlled ID but does not match the strict grammar")
                malformed += 1
    if malformed == 0:
        report.ok(check, "no malformed controlled-ID-like headings found")

    # Category breakdown, computed from the same STRICT_ID_FULLMATCH_RES
    # grammar used everywhere else in this module, so the requirement-ID
    # subtotal (plain DS-<DOMAIN>-NNN plus compound DS-API-<DOMAIN>-NNN) and
    # the full inventory total (adding DS-NNN volumes, ADR-NNN, DSF-NNN) can
    # never silently drift apart from how those IDs are actually defined.
    ids = list(id_to_files.keys())
    volumes = [i for i in ids if re.match(r"^DS-\d{3}$", i)]
    adrs = [i for i in ids if re.match(r"^ADR-\d{3}$", i)]
    dsf_docs = [i for i in ids if re.match(r"^DSF-\d{3}$", i)]
    plain_requirements = [i for i in ids if re.match(r"^DS-[A-Z]{2,8}-\d{3}$", i)]
    compound_requirements = [i for i in ids if re.match(r"^DS-(?:[A-Z]{2,8}-){2,}\d{3}$", i)]
    requirement_total = len(plain_requirements) + len(compound_requirements)

    report.ok(
        check,
        f"category breakdown — DS-NNN volumes: {len(volumes)}, ADR-NNN: {len(adrs)}, "
        f"DSF-NNN (publication): {len(dsf_docs)}, plain DS-<DOMAIN>-NNN requirements: {len(plain_requirements)}, "
        f"compound DS-API-<DOMAIN>-NNN requirements: {len(compound_requirements)}",
    )
    report.ok(check, f"requirement-ID-only subtotal (plain + compound): {requirement_total}")
    report.ok(check, f"controlled-ID inventory total (all categories): {len(id_to_files)} unique definition(s) dynamically derived from repository content")


def check_controlled_id_references(report: Report) -> None:
    check = "controlled-id-references"
    defined = collect_controlled_definitions()
    if not defined:
        report.warn(check, "no controlled-ID definitions found under docs/codex or docs/publication — skipping reference resolution")
        return
    files = _iter_markdown_files(PUBLICATION_DIRS, TEMPLATE_DIR_PREFIXES)
    unresolved = 0
    resolved = 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in CONTROLLED_ID_RE.finditer(text):
            token = m.group(1)
            if token in defined:
                resolved += 1
                continue
            unresolved += 1
            line_no = text.count("\n", 0, m.start()) + 1
            report.fail(check, f"{repo_relative(f)}:{line_no}: unresolved controlled-ID reference '{token}' (no matching heading found in docs/codex or docs/publication)")
    if unresolved == 0:
        report.ok(check, f"all {resolved} controlled-ID reference(s) resolved against {len(defined)} known definitions (templates/ excluded — placeholder IDs there never match the digit pattern)")


# ---------------------------------------------------------------------------
# HIGH4-B: General Markdown-table validation
# ---------------------------------------------------------------------------

# A *candidate* delimiter cell contains only decorative punctuation
# (colon/hyphen and common wrong-character mistakes like '*'/'='/'~') —
# deliberately permissive so malformed attempts are still detected as
# "someone tried to write a delimiter row here" rather than silently
# falling through as ordinary prose and never being validated at all.
DELIM_CANDIDATE_CELL_RE = re.compile(r"^[\s:\-*=~]*$")
# A *valid* Markdown delimiter cell: optional leading/trailing ':',
# at least three '-' in between, nothing else.
DELIM_CELL_STRICT_RE = re.compile(r"^:?-{3,}:?$")


def _split_table_row(line: str) -> list:
    """Split a Markdown table row on unescaped '|' only — '\\|' is treated
    as a literal pipe inside a cell, never a column separator."""
    placeholder = "\x00"
    protected = line.strip().replace("\\|", placeholder)
    cells = protected.split("|")
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.replace(placeholder, "|").strip() for c in cells]


def _looks_like_delimiter_candidate_row(line: str) -> bool:
    """True if this row *appears intended* as a table delimiter row — every
    cell consists only of decorative punctuation. This intentionally also
    matches malformed attempts (too few hyphens, wrong characters) so they
    get strictly validated and FAILed, rather than silently treated as
    "not a table" and skipped."""
    s = line.strip()
    if not s.startswith("|"):
        return False
    cells = _split_table_row(s)
    return bool(cells) and all(DELIM_CANDIDATE_CELL_RE.match(c) for c in cells)


def _delimiter_cell_defect_reason(cell: str) -> str:
    core = cell[1:] if cell.startswith(":") else cell
    core = core[:-1] if core.endswith(":") else core
    if any(ch != "-" for ch in core) or core == "":
        return "invalid character(s) — only a leading/trailing ':' and '-' in between are allowed"
    if core.count("-") < 3:
        return "too few hyphens (minimum 3 required, e.g. '---', ':---', '---:', ':---:')"
    return "malformed delimiter cell"


def check_markdown_tables(report: Report) -> None:
    check = "markdown-table-validation"
    files = _iter_markdown_files(PUBLICATION_DIRS)
    for f in files:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        rel = repo_relative(f)
        i = 0
        in_fence = False
        while i < len(lines):
            line = lines[i]
            if line.strip().startswith("```"):
                in_fence = not in_fence
                i += 1
                continue
            if in_fence:
                i += 1
                continue
            if line.strip().startswith("|") and i + 1 < len(lines) and _looks_like_delimiter_candidate_row(lines[i + 1]):
                header_cells = _split_table_row(line)
                delim_cells = _split_table_row(lines[i + 1])
                ncols = len(header_cells)
                malformed = False

                if len(delim_cells) != ncols:
                    report.fail(check, f"{rel}:{i + 2}: delimiter row has {len(delim_cells)} cell(s), expected {ncols} (matching header at line {i + 1})")
                    malformed = True

                for idx, cell in enumerate(delim_cells):
                    if not DELIM_CELL_STRICT_RE.match(cell):
                        report.fail(check, f"{rel}:{i + 2}: delimiter cell {idx + 1} ('{cell}') is malformed — {_delimiter_cell_defect_reason(cell)}")
                        malformed = True

                j = i + 2
                bad_rows = 0
                good_rows = 0
                while j < len(lines) and lines[j].strip().startswith("|"):
                    row_cells = _split_table_row(lines[j])
                    if len(row_cells) != ncols:
                        report.fail(check, f"{rel}:{j + 1}: table row has {len(row_cells)} column(s), expected {ncols} (header set at line {i + 1}) — check for an unescaped '|' inside a cell")
                        bad_rows += 1
                    else:
                        good_rows += 1
                    j += 1

                if not malformed and bad_rows == 0:
                    report.ok(check, f"{rel}:{i + 1}: table delimiter valid, column-count consistent ({ncols} columns, {good_rows} body row(s))")
                i = j
                continue
            i += 1
    if not any(finding.check == check and finding.severity == "FAIL" for finding in report.findings):
        report.ok(check, "Markdown-table structural scan complete — all detected tables have consistent column counts and valid delimiter rows")


# ---------------------------------------------------------------------------
# HIGH4-C: Mermaid structural validation (repository-local, not parser-backed)
# ---------------------------------------------------------------------------

SUPPORTED_DIAGRAM_DECLARATIONS = (
    "graph ", "flowchart ", "stateDiagram-v2", "stateDiagram",
    "sequenceDiagram", "classDiagram", "erDiagram",
)

# Explicit, closed allowlist of edge/arrow tokens actually used by this
# repository's controlled Mermaid sources. Any arrow-like token outside this
# set is rejected — this is a fixed set of exact strings compared with `in`,
# never a permissive regex that would accept arbitrary punctuation.
APPROVED_EDGE_TOKENS = frozenset({"<-.->", "-.->", "<-->", "-->", "==>", "---"})

# Deliberately broad "something arrow-shaped is here" detector, used only to
# *find* candidate tokens (including malformed/unsupported ones) so they can
# be checked against APPROVED_EDGE_TOKENS above — never used by itself to
# decide a token is valid.
ARROW_CANDIDATE_RE = re.compile(r"(\w+)\s*([<>=~.\-]{2,})\s*(\w+)")
BARE_ARROW_TOKEN_RE = re.compile(r"[<>=~.\-]{2,}")
LABEL_RE = re.compile(r'\|"([^"]*)"\|')
INLINE_NODE_DECL_RE = re.compile(r"(\w+)(?:\[[^\]]*\]|\([^)]*\)|\{[^}]*\})")
# stateDiagram-v2 declares a state as `StateID: description text`, not with
# a bracket — a distinct, equally-explicit declaration form.
STATE_COLON_DECL_RE = re.compile(r"^\s*(\w+)\s*:\s*\S")
FIGURE_HEADER_RE = re.compile(r"^%%\s*Figure\s+(\d{1,2})\s*[—-]\s*(.+)$")
# Mermaid's literal `[*]` start/end pseudo-state (stateDiagram-v2) needs no
# declaration by definition; substituted for a word-token placeholder before
# noise-stripping so it survives as a valid, always-declared arrow endpoint
# instead of being erased by the bracket-content strip along with real labels.
STATE_START_END_TOKEN = "__MERMAID_STATE_STARTEND__"


def _mermaid_files(report: Report):
    src_dir = resolve_repo_path(DIAGRAM_SOURCE_DIR)
    if not src_dir.is_dir():
        report.warn("mermaid-structural-validation", f"{DIAGRAM_SOURCE_DIR} does not exist — nothing to check")
        return []
    return sorted(src_dir.glob("*.mmd"))


def _check_balanced(text: str, rel: str, report: Report, check: str) -> bool:
    pairs = {"]": "[", ")": "(", "}": "{"}
    stack = []
    ok = True
    for i, ch in enumerate(text):
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack[-1] != pairs[ch]:
                report.fail(check, f"{rel}: unbalanced bracket near position {i} ('{ch}' with no matching opener)")
                ok = False
                break
            stack.pop()
    if stack:
        report.fail(check, f"{rel}: {len(stack)} unclosed bracket(s) at end of file")
        ok = False
    if text.count('"') % 2 != 0:
        report.fail(check, f"{rel}: odd number of double-quote characters (unbalanced quoted label)")
        ok = False
    return ok


def _strip_inline_noise(line: str) -> str:
    """Remove bracket/paren/brace-delimited content, quoted strings, and
    bare '|' label delimiters, so that a real arrow token between two node
    IDs is left directly adjacent to them and detectable by a simple
    two-sided regex, without a combinatorial inline-declaration-aware
    arrow pattern. Mermaid's literal `[*]` start/end marker is preserved
    (as a word-token placeholder) rather than erased along with real
    bracketed labels."""
    cleaned = line.replace("[*]", STATE_START_END_TOKEN)
    cleaned = re.sub(r"\[[^\]]*\]|\([^)]*\)|\{[^}]*\}|\"[^\"]*\"", " ", cleaned)
    return cleaned.replace("|", " ")


def _collect_declared_nodes(numbered_lines) -> set:
    """A node is declared only by an explicit bracket/paren/brace
    declaration (`ID["label"]`, `ID(label)`, `ID{label}`), a stateDiagram-v2
    colon declaration (`ID: description`), inline or on its own line — never
    merely by appearing as a bare edge endpoint. A `subgraph ID["..."]` or
    `state ID { ... }` line's ID is a subgraph/composite-state name, not a
    plain node declaration, and is excluded. Mermaid's `[*]` pseudo-state is
    always implicitly declared (see STATE_START_END_TOKEN)."""
    declared = {STATE_START_END_TOKEN}
    for _lineno, line in numbered_lines:
        stripped = line.strip()
        if stripped.startswith("subgraph") or stripped.startswith("state "):
            continue
        for m in INLINE_NODE_DECL_RE.finditer(line):
            declared.add(m.group(1))
        sm = STATE_COLON_DECL_RE.match(line)
        if sm:
            declared.add(sm.group(1))
    return declared


def _parse_mermaid_edges(numbered_lines, declared: set, rel: str, report: Report, check: str) -> list:
    """Return a list of (src, arrow, dst, label) for every edge whose arrow
    token is in APPROVED_EDGE_TOKENS. Any arrow-like token outside the
    allowlist is reported as a FAIL with file:line and excluded from the
    returned edges (never silently accepted or silently dropped without a
    finding). An approved-token edge referencing a node with no explicit
    declaration is also reported as a FAIL with file:line — the edge is
    still returned so figure-specific semantic checks can evaluate it
    independently of the declaration defect."""
    edges = []
    for lineno, line in numbered_lines:
        label_match = LABEL_RE.search(line)
        label = label_match.group(1) if label_match else None
        cleaned = _strip_inline_noise(line)

        matched_spans = []
        for m in ARROW_CANDIDATE_RE.finditer(cleaned):
            src, arrow, dst = m.group(1), m.group(2), m.group(3)
            matched_spans.append(m.span(2))
            if arrow not in APPROVED_EDGE_TOKENS:
                report.fail(check, f"{rel}:{lineno}: edge uses an unapproved arrow token '{arrow}' (allowed: {sorted(APPROVED_EDGE_TOKENS)})")
                continue
            if src not in declared:
                report.fail(check, f"{rel}:{lineno}: edge references undeclared node '{src}'")
            if dst not in declared:
                report.fail(check, f"{rel}:{lineno}: edge references undeclared node '{dst}'")
            edges.append((src, arrow, dst, label))

        # An arrow-shaped token with no word immediately reachable on one
        # side (line starts with an arrow, or nothing but whitespace
        # follows it) can't be captured by the two-sided pattern above —
        # check separately so a genuinely empty endpoint is still flagged.
        for tm in BARE_ARROW_TOKEN_RE.finditer(cleaned):
            if tm.span() in matched_spans:
                continue
            token = tm.group(0)
            if token not in APPROVED_EDGE_TOKENS:
                continue
            before, after = cleaned[: tm.start()], cleaned[tm.end():]
            if not re.search(r"\w\s*$", before) or not re.search(r"^\s*\w", after):
                report.fail(check, f"{rel}:{lineno}: edge with an empty endpoint near '{token}'")

    return edges


def _figure16_semantic_check(edges, rel: str, report: Report, check: str) -> None:
    """Figure 16 (DS-013 vs DS-014 Boundary) must show two structurally and
    semantically distinct relationships between the same two nodes: a
    one-way Promotion edge (Idea --> Backlog only, labeled "Promotion" and
    stating the approved-controlling-process requirement) and a separate
    bidirectional Cross-reference edge (labeled "Cross-reference", never
    "Promotion"). Swapped, missing, duplicated, or reversed labels all fail."""

    def has_word(label, word):
        return bool(label) and word.lower() in label.lower()

    idea_backlog_edges = [(s, a, d, l) for (s, a, d, l) in edges if {s, d} == {"Idea", "Backlog"}]
    one_way = [e for e in idea_backlog_edges if e[1] == "-->" and e[0] == "Idea" and e[2] == "Backlog"]
    reverse_one_way = [e for e in idea_backlog_edges if e[1] == "-->" and e[0] == "Backlog" and e[2] == "Idea"]
    bidirectional = [e for e in idea_backlog_edges if e[1] in ("<-->", "<-.->")]

    ok = True

    if len(one_way) != 1:
        report.fail(check, f"{rel}: expected exactly one one-way Idea-->Backlog promotion edge, found {len(one_way)}")
        ok = False
    if reverse_one_way:
        report.fail(check, f"{rel}: found a one-way Backlog-->Idea edge — promotion must never run backward into DS-014")
        ok = False
    if len(bidirectional) != 1:
        report.fail(check, f"{rel}: expected exactly one separate bidirectional cross-reference edge, found {len(bidirectional)}")
        ok = False

    if len(one_way) == 1:
        promo_label = one_way[0][3]
        if not has_word(promo_label, "Promotion"):
            report.fail(check, f"{rel}: one-way Idea-->Backlog edge is missing/mislabeled — expected a 'Promotion' label, found {promo_label!r}")
            ok = False
        elif not has_word(promo_label, "approved"):
            report.fail(check, f"{rel}: Promotion edge label does not state the approved-controlling-process requirement (found {promo_label!r})")
            ok = False
        if has_word(promo_label, "Cross-reference"):
            report.fail(check, f"{rel}: one-way Promotion edge is incorrectly labeled Cross-reference (swapped labels)")
            ok = False

    if len(bidirectional) == 1:
        xref_label = bidirectional[0][3]
        if not has_word(xref_label, "Cross-reference"):
            report.fail(check, f"{rel}: bidirectional edge is missing/mislabeled — expected a 'Cross-reference' label, found {xref_label!r}")
            ok = False
        if has_word(xref_label, "Promotion"):
            report.fail(check, f"{rel}: bidirectional edge is incorrectly labeled Promotion — a promotion must be one-way, never a bidirectional edge (swapped labels or bidirectional-promotion defect)")
            ok = False

    if len(one_way) == 1 and len(bidirectional) == 1:
        if has_word(one_way[0][3], "Promotion") and has_word(bidirectional[0][3], "Promotion"):
            report.fail(check, f"{rel}: both edges are labeled Promotion — expected exactly one Promotion edge and one Cross-reference edge")
            ok = False

    if ok:
        report.ok(check, f"{rel}: confirmed a correctly-labeled one-way Promotion edge and a separate, correctly-labeled bidirectional Cross-reference edge")


def check_mermaid_sources(report: Report) -> None:
    check = "mermaid-structural-validation"
    files = _mermaid_files(report)
    register_rows = check_diagram_register_schema(Report())  # isolated re-parse, no duplicate findings emitted

    for f in files:
        rel = repo_relative(f)
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        # Figure ID/title metadata
        header_match = FIGURE_HEADER_RE.match(lines[0]) if lines else None
        if not header_match:
            report.fail(check, f"{rel}: first line is not a '%% Figure N — Title' metadata comment")
        else:
            report.ok(check, f"{rel}: Figure {header_match.group(1)} metadata present")

        # filename matches expected Diagram Register source path
        if register_rows and header_match:
            fig_num = int(header_match.group(1))
            row = register_rows.get(fig_num)
            if row:
                expected = row.get("Source Path", "")
                if f"/{f.name}`" not in expected and f.name not in expected:
                    report.fail(check, f"{rel}: filename does not match Diagram Register row {fig_num}'s Source Path ('{expected}')")
                else:
                    report.ok(check, f"{rel}: filename matches Diagram Register row {fig_num}")

        # accessibility description (structural presence check; full check_accessibility_descriptions covers length)
        if "Accessibility description" not in text:
            report.fail(check, f"{rel}: missing 'Accessibility description' comment block")

        # supported diagram declaration
        numbered_lines = [
            (i + 1, ln) for i, ln in enumerate(lines)
            if ln.strip() and not ln.strip().startswith("%%")
        ]
        body_text = "\n".join(ln for _no, ln in numbered_lines)
        if not numbered_lines or not any(numbered_lines[0][1].strip().startswith(d) for d in SUPPORTED_DIAGRAM_DECLARATIONS):
            report.fail(check, f"{rel}: no supported diagram declaration found as the first non-comment line (expected one of {SUPPORTED_DIAGRAM_DECLARATIONS})")
        else:
            report.ok(check, f"{rel}: supported diagram declaration present")

        _check_balanced(body_text, rel, report, check)

        declared = _collect_declared_nodes(numbered_lines)
        fails_before = sum(1 for finding in report.findings if finding.check == check and finding.severity == "FAIL")
        edges = _parse_mermaid_edges(numbered_lines, declared, rel, report, check)
        fails_after = sum(1 for finding in report.findings if finding.check == check and finding.severity == "FAIL")
        if edges and fails_after == fails_before:
            report.ok(check, f"{rel}: {len(edges)} edge(s) use approved arrow tokens and explicitly-declared node IDs")

        # --- Figure-specific semantic scans -----------------------------
        if header_match and header_match.group(1) == "5":
            forbidden = [
                (s, a, d) for (s, a, d, _l) in edges
                if {s, d} & {"Sage"} and {s, d} & {"Exec", "Broker"}
            ]
            if forbidden:
                report.fail(check, f"{rel}: found a Sage<->Execution/Broker edge, which is prohibited: {forbidden}")
            else:
                report.ok(check, f"{rel}: confirmed no Sage-to-Execution or Sage-to-Broker edge exists")

        if header_match and header_match.group(1) == "16":
            _figure16_semantic_check(edges, rel, report, check)

        if "trade-validation-pipeline" in f.name:
            id_to_label = {}
            for dm in re.finditer(r'(\w+)\["([^"]+)"\]', body_text):
                id_to_label.setdefault(dm.group(1), dm.group(2))
            ordered_ids = []
            seen = set()
            for src, arrow, dst, _label in edges:
                for node in (src, dst):
                    if node not in seen:
                        ordered_ids.append(node)
                        seen.add(node)
            stage_labels = [id_to_label.get(n) for n in ordered_ids if id_to_label.get(n)]
            canon = resolve_repo_path("docs/pipeline-stages.txt")
            canonical = canon.read_text(encoding="utf-8").splitlines() if canon.is_file() else []
            if canonical and stage_labels == canonical:
                report.ok(check, f"{rel}: pipeline stage order matches docs/pipeline-stages.txt exactly ({len(canonical)}/{len(canonical)})")
            else:
                report.fail(check, f"{rel}: pipeline stage order does not match docs/pipeline-stages.txt exactly (found {len(stage_labels)} stage(s), expected {len(canonical)})")


REQUIRED_TOOLING_FILES = [
    "scripts/publication/README.md",
    "scripts/publication/requirements.txt",
    "scripts/publication/validate_publication.py",
    "scripts/publication/generate_manifest.py",
    "scripts/publication/record_baseline.py",
    "scripts/publication/checksum_artifacts.py",
    "scripts/publication/tests/test_publication_tools.py",
]


def check_tooling_self_check(report: Report) -> None:
    check = "publication-tooling-self-check"
    for rel in REQUIRED_TOOLING_FILES:
        if resolve_repo_path(rel).is_file():
            report.ok(check, f"{rel} present")
        else:
            report.fail(check, f"{rel} MISSING")


def run_all() -> Report:
    report = Report()
    check_tooling_self_check(report)
    check_controlled_metadata(report)
    check_markdown_headings(report)
    check_relative_links(report)
    check_dsf_id_uniqueness(report)
    rows = check_diagram_register_schema(report)
    check_diagram_path_truthfulness(report, rows)
    check_figure_placeholders(report)
    check_accessibility_descriptions(report)
    manifest = check_manifest_json(report)
    check_manifest_generated_truthfulness(report, manifest)
    check_no_absolute_personal_paths(report)
    check_no_secrets(report)
    check_no_unsupported_proprietary_font(report)
    check_contrast_ratios(report)
    check_controlled_id_references(report)
    check_controlled_id_inventory(report)
    check_markdown_tables(report)
    check_mermaid_sources(report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a text report.")
    parser.add_argument("--quiet", action="store_true", help="Only print FAIL/WARN findings, not OK.")
    args = parser.parse_args(argv)

    report = run_all()

    if args.json:
        print(json.dumps([f.__dict__ for f in report.findings], indent=2))
    else:
        for f in report.findings:
            if args.quiet and f.severity == "OK":
                continue
            print(f"[{f.severity:4}] {f.check}: {f.message}")
        n_fail = sum(1 for f in report.findings if f.severity == "FAIL")
        n_warn = sum(1 for f in report.findings if f.severity == "WARN")
        n_ok = sum(1 for f in report.findings if f.severity == "OK")
        print()
        print(f"Summary: {n_ok} OK, {n_warn} WARN, {n_fail} FAIL")

    return 1 if report.has_failures else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
