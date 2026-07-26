#!/usr/bin/env python3
"""Validate the DarkSage publication state register in docs/publication.

Verifies, for every Released volume: file existence, genuine DOCX (ZIP/OOXML)
and PDF format, manifest membership (the docx/pdf entry exists, is marked
generated, and its planned_artifact_path matches the register), byte-count
and SHA-256 integrity against the actual file on disk, and that the
evidence-completeness fields are grounded (affirmative) rather than assumed
from a bare "Yes" string. DS-001 through DS-014 (the Core Codex) predate this
register and are exempt only from approved_by/approved_date, per
docs/publication/PUBLICATION_PROMOTION_RULES.md; every other requirement
still applies to them.

Standard library plus pypdf (already present in scripts/publication/.venv)
for PDF structural parsing, when available. No network access. Exits 0 only
if no FAIL-level finding was produced.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from _repo import resolve_repo_path, sha256_of_file

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - environment without pypdf installed
    PdfReader = None

STATE_REGISTER = "docs/publication/PUBLICATION_STATE_REGISTER.csv"
MANIFEST_PATH = "docs/publication/PUBLICATION_MANIFEST.json"
ALLOWED_PUBLICATION_STATE = {
    "Released",
    "Approved for Publication",
    "Publication In Progress",
    "Draft",
    "Skeleton",
    "Blocked",
    "Deprecated",
    "Superseded",
}

# DS-001..DS-014 were released before this register existed; their approval
# history predates approved_by/approved_date tracking (see
# PUBLICATION_PROMOTION_RULES.md § Legacy Core Volumes). No other release
# requirement is waived for them.
LEGACY_CORE_VOLUME_MAX = 14

AFFIRMATIVE = {"yes", "true", "1"}


@dataclass
class Finding:
    severity: str
    check: str
    message: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

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


def _resolve_csv(path: str) -> Path:
    return resolve_repo_path(path)


def _read_rows() -> list[dict[str, str]]:
    path = _resolve_csv(STATE_REGISTER)
    with path.open("r", encoding="utf-8", newline="") as f:
        return [row for row in csv.DictReader(f)]


def _is_safe_path(value: str) -> bool:
    if not value:
        return False
    if value.startswith("/") or value.startswith("\\"):
        return False
    if ".." in value:
        return False
    return True


def _volume_number(volume_id: str) -> Optional[int]:
    if not volume_id.startswith("DS-"):
        return None
    try:
        return int(volume_id.split("-")[1])
    except ValueError:
        return None


def _is_affirmative(value: str) -> bool:
    return value.strip().lower() in AFFIRMATIVE


def _is_genuine_docx(path: Path) -> tuple[bool, str]:
    """A genuine DOCX is a ZIP/OOXML package containing the two files every
    real Word document must have. A renamed .txt file or truncated archive
    fails here even though it "exists" at the recorded path."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return False, "not a valid ZIP/OOXML package (bad ZIP signature)"
    except OSError as exc:
        return False, f"could not open file: {exc}"
    if "[Content_Types].xml" not in names:
        return False, "ZIP package missing [Content_Types].xml"
    if "word/document.xml" not in names:
        return False, "ZIP package missing word/document.xml"
    return True, ""


def _is_genuine_pdf(path: Path) -> tuple[bool, str]:
    """A genuine PDF begins with a %PDF- signature and, when pypdf is
    available, must actually parse as a PDF (catches a truncated or
    corrupted file that merely has the right first five bytes)."""
    try:
        with path.open("rb") as fh:
            header = fh.read(8)
    except OSError as exc:
        return False, f"could not open file: {exc}"
    if not header.startswith(b"%PDF-"):
        return False, "missing %PDF- signature"
    if PdfReader is not None:
        try:
            reader = PdfReader(str(path))
            _ = len(reader.pages)
        except Exception as exc:  # noqa: BLE001 - any parse failure is a genuine defect
            return False, f"signature present but file could not be parsed as a PDF: {exc}"
    return True, ""


def _load_manifest(report: Report) -> Optional[dict]:
    check = "publication-manifest-loadable"
    path = resolve_repo_path(MANIFEST_PATH)
    if not path.is_file():
        report.fail(check, f"{MANIFEST_PATH} does not exist")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.fail(check, f"{MANIFEST_PATH} is not valid JSON: {exc}")
        return None
    entries = data.get("entries")
    if not isinstance(entries, list):
        report.fail(check, f"{MANIFEST_PATH} has no 'entries' list")
        return None
    report.ok(check, f"{MANIFEST_PATH} parses as JSON with {len(entries)} entries")
    return data


def _manifest_entry(manifest: Optional[dict], document_id: str, artifact_type: str) -> Optional[dict]:
    if not manifest:
        return None
    for entry in manifest.get("entries", []):
        if entry.get("document_id") == document_id and entry.get("artifact_type") == artifact_type:
            return entry
    return None


def check_state_register_exists(report: Report) -> None:
    path = resolve_repo_path(STATE_REGISTER)
    if not path.is_file():
        report.fail("publication-state-register-exists", f"{STATE_REGISTER} does not exist")


def check_state_schema(report: Report, rows: list[dict[str, str]]) -> None:
    check = "publication-state-schema"
    path = resolve_repo_path(STATE_REGISTER)
    with path.open("r", encoding="utf-8", newline="") as f:
        header = csv.DictReader(f).fieldnames or []
    required = [
        "volume_id", "title", "publication_state", "markdown_path", "docx_path",
        "pdf_path", "metadata_verified", "traceability_complete", "controlled_ids_valid",
        "acceptance_criteria_complete", "independent_review_complete", "independent_review_evidence",
        "checksum_verified", "release_manifest_entry", "approved_by", "approved_date", "blocker", "notes",
    ]
    missing = [col for col in required if col not in header]
    if missing:
        report.fail(check, f"{STATE_REGISTER} missing columns: {missing}")
    else:
        report.ok(check, f"{STATE_REGISTER} has all {len(required)} required columns")


def check_duplicate_volumes(report: Report, rows: list[dict[str, str]]) -> None:
    check = "publication-duplicate-volume"
    seen: set[str] = set()
    dup = False
    for i, row in enumerate(rows):
        vid = row.get("volume_id", "").strip()
        if not vid:
            report.fail(check, f"row {i+2} missing volume_id")
        elif vid in seen:
            report.fail(check, f"duplicate volume_id: {vid}")
            dup = True
        else:
            seen.add(vid)
    if not dup:
        report.ok(check, f"no duplicate volume_id values across {len(rows)} row(s)")


def check_volume_range(report: Report, rows: list[dict[str, str]]) -> None:
    check = "publication-volume-range"
    for i, row in enumerate(rows):
        vid = row.get("volume_id", "").strip()
        if not vid:
            continue
        if vid.startswith("DS-"):
            num = _volume_number(vid)
            if num is None:
                report.fail(check, f"row {i+2} malformed volume_id: {vid}")
            elif num > 23:
                report.fail(check, f"row {i+2} references unsupported volume: {vid}")


def check_required_states(report: Report, rows: list[dict[str, str]]) -> None:
    check = "publication-required-states"
    expected = {f"DS-{i:03d}" for i in range(1, 24)}
    present = {row.get("volume_id", "").strip() for row in rows if row.get("volume_id", "").strip()}
    missing = sorted(expected - present)
    if missing:
        report.fail(check, f"missing expected publication volume rows: {missing}")
    extra = sorted(present - expected)
    if extra:
        report.fail(check, f"unexpected publication volume rows: {extra}")
    if not missing and not extra:
        report.ok(check, "DS-001 through DS-023 are each present exactly once")


def check_safe_paths(report: Report, rows: list[dict[str, str]]) -> None:
    check = "publication-path-safety"
    for i, row in enumerate(rows):
        for field_name in ["markdown_path", "docx_path", "pdf_path", "release_manifest_entry"]:
            value = row.get(field_name, "").strip()
            if value and not _is_safe_path(value):
                report.fail(check, f"row {i+2} has unsafe {field_name}: {value}")
            if field_name == "markdown_path" and value:
                try:
                    path = resolve_repo_path(value)
                except Exception:
                    report.fail(check, f"row {i+2} markdown_path path traversal or invalid: {value}")
                    continue
                if not path.is_file():
                    report.fail(check, f"row {i+2} markdown_path does not exist: {value}")


def check_state_values(report: Report, rows: list[dict[str, str]]) -> None:
    check = "publication-state-values"
    for i, row in enumerate(rows):
        state = row.get("publication_state", "").strip()
        if state and state not in ALLOWED_PUBLICATION_STATE:
            report.fail(check, f"row {i+2} has invalid publication_state: {state}")


def _check_released_row(report: Report, i: int, row: dict[str, str], manifest: Optional[dict]) -> None:
    check = "publication-release-artifacts"
    volume_id = row.get("volume_id", "").strip()
    volume_number = _volume_number(volume_id)
    is_legacy_core_volume = volume_number is not None and volume_number <= LEGACY_CORE_VOLUME_MAX

    for field_name, artifact_type in (("markdown_path", "markdown"), ("docx_path", "docx"), ("pdf_path", "pdf")):
        value = row.get(field_name, "").strip()
        if not value:
            report.fail(check, f"row {i+2} ({volume_id}) Released but missing {field_name}")
            continue
        if not _is_safe_path(value):
            report.fail(check, f"row {i+2} ({volume_id}) Released has unsafe {field_name}: {value}")
            continue
        path = resolve_repo_path(value)
        if not path.is_file():
            report.fail(check, f"row {i+2} ({volume_id}) Released path does not exist: {value}")
            continue

        genuine = True
        if artifact_type != "markdown":
            genuine, reason = _is_genuine_docx(path) if artifact_type == "docx" else _is_genuine_pdf(path)
            if not genuine:
                report.fail(check, f"row {i+2} ({volume_id}) {field_name} is not a genuine {artifact_type.upper()}: {reason}")
                continue

        entry = _manifest_entry(manifest, volume_id, artifact_type)
        if entry is None:
            report.fail(check, f"row {i+2} ({volume_id}) has no {artifact_type} entry for it in {MANIFEST_PATH}")
            continue
        if entry.get("planned_artifact_path") != value:
            report.fail(
                check,
                f"row {i+2} ({volume_id}) manifest {artifact_type} entry path "
                f"'{entry.get('planned_artifact_path')}' does not match register {field_name} '{value}'",
            )
        if not entry.get("generated"):
            report.fail(check, f"row {i+2} ({volume_id}) manifest {artifact_type} entry is not marked generated")

        actual_size = path.stat().st_size
        recorded_size = entry.get("byte_count")
        if recorded_size is not None and recorded_size != actual_size:
            report.fail(
                check,
                f"row {i+2} ({volume_id}) {artifact_type} byte_count mismatch: manifest records "
                f"{recorded_size}, actual file is {actual_size} bytes",
            )

        actual_sha = sha256_of_file(path)
        recorded_sha = entry.get("checksum")
        if recorded_sha != actual_sha:
            report.fail(
                check,
                f"row {i+2} ({volume_id}) {artifact_type} checksum mismatch: manifest records "
                f"{recorded_sha!r}, actual SHA-256 is {actual_sha!r}",
            )
        if genuine and entry is not None and entry.get("generated") and recorded_sha == actual_sha:
            report.ok(check, f"row {i+2} ({volume_id}) {artifact_type} format, manifest membership, and checksum verified")

    manifest_path_str = row.get("release_manifest_entry", "").strip()
    if not manifest_path_str:
        report.fail(check, f"row {i+2} ({volume_id}) Released but missing release_manifest_entry")
    elif not _is_safe_path(manifest_path_str):
        report.fail(check, f"row {i+2} ({volume_id}) Released has unsafe release_manifest_entry: {manifest_path_str}")
    elif not resolve_repo_path(manifest_path_str).is_file():
        report.fail(check, f"row {i+2} ({volume_id}) release_manifest_entry does not exist: {manifest_path_str}")

    # checksum_verified must be affirmative *and* corroborated by the real
    # recomputed-checksum comparison above -- the bare string is never
    # trusted on its own.
    if not _is_affirmative(row.get("checksum_verified", "")):
        report.fail(check, f"row {i+2} ({volume_id}) Released but checksum_verified is not affirmative")

    for evidence_field in (
        "metadata_verified", "traceability_complete", "controlled_ids_valid",
        "acceptance_criteria_complete", "independent_review_complete",
    ):
        if not _is_affirmative(row.get(evidence_field, "")):
            report.fail(check, f"row {i+2} ({volume_id}) Released but {evidence_field} is not affirmative")

    # independent_review_evidence must point to a real file -- this is not
    # waived by the legacy Core exception, which covers only
    # approved_by/approved_date (see PUBLICATION_PROMOTION_RULES.md).
    review_evidence = row.get("independent_review_evidence", "").strip()
    if not review_evidence:
        report.fail(check, f"row {i+2} ({volume_id}) Released but missing independent_review_evidence")
    elif not _is_safe_path(review_evidence):
        report.fail(check, f"row {i+2} ({volume_id}) Released has unsafe independent_review_evidence: {review_evidence}")
    elif not resolve_repo_path(review_evidence).is_file():
        report.fail(check, f"row {i+2} ({volume_id}) independent_review_evidence does not exist: {review_evidence}")

    if not is_legacy_core_volume:
        if not row.get("approved_by", "").strip():
            report.fail(check, f"row {i+2} ({volume_id}) Released but missing approved_by")
        if not row.get("approved_date", "").strip():
            report.fail(check, f"row {i+2} ({volume_id}) Released but missing approved_date")


def _check_draft_or_skeleton_row(report: Report, i: int, row: dict[str, str], state: str) -> None:
    check = "publication-release-artifacts"
    volume_id = row.get("volume_id", "").strip()
    for field_name in (
        "docx_path", "pdf_path", "release_manifest_entry", "approved_by", "approved_date",
        "independent_review_evidence",
    ):
        if row.get(field_name, "").strip():
            report.fail(check, f"row {i+2} ({volume_id}) {state} volume must not set {field_name}")
    for evidence_field in (
        "metadata_verified", "traceability_complete", "controlled_ids_valid",
        "acceptance_criteria_complete", "independent_review_complete",
    ):
        if _is_affirmative(row.get(evidence_field, "")):
            report.fail(check, f"row {i+2} ({volume_id}) {state} volume must not claim {evidence_field}")
    volume_number = _volume_number(volume_id)
    if volume_number is not None and 15 <= volume_number <= 23:
        if "Not Released" not in row.get("notes", ""):
            report.fail(check, f"row {i+2} ({volume_id}) expansion volume notes must state 'Not Released'")


def check_release_artifact_requirements(report: Report, rows: list[dict[str, str]], manifest: Optional[dict]) -> None:
    check = "publication-release-artifacts"
    for i, row in enumerate(rows):
        state = row.get("publication_state", "").strip()
        volume_id = row.get("volume_id", "").strip()
        volume_number = _volume_number(volume_id)

        if state == "Released":
            _check_released_row(report, i, row, manifest)
        elif state in {"Skeleton", "Draft"}:
            _check_draft_or_skeleton_row(report, i, row, state)

        if volume_number is not None and 15 <= volume_number <= 23:
            if state == "Released":
                report.fail(check, f"row {i+2} expansion volume {volume_id} must not be Released")
            elif state not in {"Skeleton", "Draft"}:
                report.fail(check, f"row {i+2} expansion volume {volume_id} state must be Skeleton or Draft, found '{state}'")


def run_all() -> Report:
    report = Report()
    check_state_register_exists(report)
    path = resolve_repo_path(STATE_REGISTER)
    if not path.is_file():
        return report
    rows = _read_rows()
    check_state_schema(report, rows)
    check_duplicate_volumes(report, rows)
    check_volume_range(report, rows)
    check_required_states(report, rows)
    check_safe_paths(report, rows)
    manifest = _load_manifest(report)
    check_release_artifact_requirements(report, rows, manifest)
    check_state_values(report, rows)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate publication state register.")
    parser.add_argument("--json", action="store_true", help="Output JSON report.")
    args = parser.parse_args(argv)
    report = run_all()
    if args.json:
        print(json.dumps({"has_failures": report.has_failures, "findings": [f.__dict__ for f in report.findings]}, indent=2))
    else:
        for finding in report.findings:
            print(f"[{finding.severity}] {finding.check}: {finding.message}")
        n_ok = sum(1 for f in report.findings if f.severity == "OK")
        n_warn = sum(1 for f in report.findings if f.severity == "WARN")
        n_fail = sum(1 for f in report.findings if f.severity == "FAIL")
        print()
        print(f"Summary: {n_ok} OK, {n_warn} WARN, {n_fail} FAIL")
    return 1 if report.has_failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
