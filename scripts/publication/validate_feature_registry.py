#!/usr/bin/env python3
"""Validate docs/features/FEATURE_REGISTRY.csv and its companion files
(FEATURE_DEPENDENCIES.csv, PLATFORM_CAPABILITY_MATRIX.csv,
EDITION_CAPABILITY_MATRIX.csv, TRADINGVIEW_CAPABILITY_COMPARISON.md) for
internal consistency, without mutating any controlled source.

Fails closed: every rule in this docstring is a FAIL-level check unless
explicitly marked WARN. Standard library only. No network access. Exits 0
only if no FAIL-level finding was produced.

Usage:
    python scripts/publication/validate_feature_registry.py
    python scripts/publication/validate_feature_registry.py --json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from _repo import repo_relative, resolve_repo_path, PathContainmentError

FEATURES_DIR = "docs/features"
REGISTRY_PATH = f"{FEATURES_DIR}/FEATURE_REGISTRY.csv"
DEPENDENCIES_PATH = f"{FEATURES_DIR}/FEATURE_DEPENDENCIES.csv"
PLATFORM_MATRIX_PATH = f"{FEATURES_DIR}/PLATFORM_CAPABILITY_MATRIX.csv"
EDITION_MATRIX_PATH = f"{FEATURES_DIR}/EDITION_CAPABILITY_MATRIX.csv"
TRADINGVIEW_PATH = f"{FEATURES_DIR}/TRADINGVIEW_CAPABILITY_COMPARISON.md"


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


REQUIRED_COLUMNS = [
    "feature_id", "feature_name", "category", "summary", "purpose",
    "owner_volume", "supporting_volumes", "implementation_status",
    "release_stage", "priority", "initial_release_required",
    "groundwork_required_now", "platform_availability", "edition_availability",
    "dependencies", "risk_level", "safety_classification", "UX_location",
    "API_or_service_owner", "acceptance_summary", "design_evidence",
    "implementation_evidence", "test_evidence", "release_evidence",
    "blocker", "tentative_start_window", "tentative_completion_window",
    "timeline_confidence", "release_history", "replacement_feature",
    "deprecation_notes",
]

ALLOWED_STATUSES = {
    "Idea", "Future", "Planned", "Designed", "In Development", "Implemented",
    "Tested", "Released", "Blocked", "Deprecated", "Removed",
}
ACTIVE_STATUSES = {
    "Idea", "Planned", "Designed", "In Development", "Implemented", "Tested", "Released",
}

ALLOWED_STAGES = {
    "Stage 0 -- Codex and Architecture",
    "Stage 1 -- Local Technical Foundation",
    "Stage 2 -- Usable Paper-Trading Alpha",
    "Stage 3 -- Founder Workstation Beta",
    "Stage 4 -- Customer Cloud Beta",
    "Stage 5 -- Initial Commercial Release",
    "Stage 6 -- Advanced Trading Expansion",
    "Stage 7 -- Platform and TradingView-Style Expansion",
    "Stage 8 -- Strategy Ecosystem and Private Collaboration",
    "Stage 9 -- Marketplace, Global, and Institutional Expansion",
}

ALLOWED_GROUNDWORK = {
    "Groundwork Required Now",
    "Can Be Added Later Without Current Architectural Work",
    "Explicitly Rejected",
    "Decision Pending",
}

ALLOWED_SAFETY = {
    "Deterministic-Authoritative",
    "Advisory (Sage, non-authoritative)",
    "Informational",
    "N/A",
}
NON_AUTHORITATIVE_SAFETY = {"N/A", "Informational", "Advisory (Sage, non-authoritative)", ""}

ALLOWED_EDITIONS = {"Founder", "Customer", "N/A"}
ALLOWED_PLATFORMS = {"Windows", "macOS", "Linux", "Web", "iOS", "Android", "N/A"}
CLIENT_PLATFORMS = ("Windows", "macOS", "Linux", "Web", "iOS", "Android")

VOLUME_RE = re.compile(r"^DS-0(?:0[1-9]|1[0-9]|2[0-3])$")  # DS-001..DS-023, fully anchored
VALID_VOLUMES = {f"DS-0{n:02d}" for n in range(1, 24)}

EXIT_MANAGEMENT_CATEGORY = "14 Stop loss and take profit"
ORDER_EXECUTION_CATEGORY = "15 Order management and execution"

# Feature rows whose exit-management/order-execution content genuinely
# implicates order lifecycle, broker acknowledgement, partial fills,
# cancel/replace, reconciliation, stale/unknown order state, recovery after
# outage, duplicate prevention, idempotency, failure handling, or gap/
# slippage reporting -- and therefore must carry a DS-023 dependency
# (supporting_volumes or dependencies). Hand-curated during the 2026-07-26
# audit repair; not a mechanically-derived total.
REQUIRES_DS023 = {
    "FEAT-0170", "FEAT-0171", "FEAT-0172", "FEAT-0178", "FEAT-0179",
    "FEAT-0180", "FEAT-0181", "FEAT-0183", "FEAT-0185", "FEAT-0186",
    "FEAT-0187", "FEAT-0188", "FEAT-0189", "FEAT-0192",
}

# Mobile/platform-specific exit-management interaction features that must
# carry a DS-016 and/or DS-022 dependency.
REQUIRES_DS016_OR_DS022 = {
    "FEAT-0182", "FEAT-0183", "FEAT-0184", "FEAT-0031", "FEAT-0032",
}

FOUNDER_DESKTOP_ONLY_FEATURES = {"FEAT-0122", "FEAT-0135", "FEAT-0268"}

TV_ID_RE = re.compile(r"\bFEAT-\d{4}\b")
TV_ROW_RE = re.compile(r"^\| (.+?) \| ([A-E]) \| (FEAT-\d{4}) \| (.*?) \|$", re.MULTILINE)


def _load_csv(report: Report, rel_path: str, check: str):
    try:
        path = resolve_repo_path(rel_path)
    except PathContainmentError as exc:
        report.fail(check, f"{rel_path}: {exc}")
        return None
    if not path.is_file():
        report.fail(check, f"{rel_path} does not exist")
        return None
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def _load_registry(report: Report):
    rows = _load_csv(report, REGISTRY_PATH, "registry-exists")
    if rows is None:
        return None
    report.ok("registry-exists", f"{REGISTRY_PATH} parses as CSV with {len(rows)} rows")
    return rows


def check_schema(report: Report, rows) -> None:
    check = "schema-complete"
    if not rows:
        report.fail(check, "registry has zero rows")
        return
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
    if missing_cols:
        report.fail(check, f"missing required column(s): {missing_cols}")
        return
    for r in rows:
        fid = r.get("feature_id", "?")
        for mandatory in ("feature_id", "feature_name", "category", "owner_volume",
                          "implementation_status", "release_stage", "groundwork_required_now"):
            if not r.get(mandatory, "").strip():
                report.fail(check, f"{fid}: mandatory field '{mandatory}' is empty")
    report.ok(check, f"all {len(REQUIRED_COLUMNS)} required columns present; mandatory fields checked for {len(rows)} rows")


def check_unique_ids(report: Report, rows) -> set:
    check = "unique-feature-ids"
    seen: dict = {}
    for row in rows:
        fid = row.get("feature_id", "")
        seen.setdefault(fid, []).append(row.get("feature_name", ""))
    dupes = {fid: names for fid, names in seen.items() if len(names) > 1}
    if dupes:
        for fid, names in dupes.items():
            report.fail(check, f"duplicate feature_id '{fid}' used by: {names}")
    else:
        report.ok(check, f"all {len(seen)} feature_id values are unique")
    return set(seen.keys())


def check_malformed_ids(report: Report, ids: set) -> None:
    check = "well-formed-feature-ids"
    bad = [fid for fid in ids if not re.fullmatch(r"FEAT-\d{4}", fid)]
    if bad:
        for fid in bad:
            report.fail(check, f"malformed feature_id: {fid!r} (expected FEAT-NNNN)")
    else:
        report.ok(check, f"all {len(ids)} feature_id values match FEAT-NNNN")


def check_controlled_vocabularies(report: Report, rows) -> None:
    check = "controlled-vocabularies"
    hit = False
    for row in rows:
        fid = row.get("feature_id", "?")
        status = row.get("implementation_status", "")
        stage = row.get("release_stage", "")
        groundwork = row.get("groundwork_required_now", "")
        safety = row.get("safety_classification", "")
        editions = [e.strip() for e in row.get("edition_availability", "").split(";") if e.strip()]
        platforms = [p.strip() for p in row.get("platform_availability", "").split(";") if p.strip()]

        if status not in ALLOWED_STATUSES:
            report.fail(check, f"{fid}: invalid implementation_status '{status}'"); hit = True
        if not stage.strip():
            report.fail(check, f"{fid}: release_stage is empty"); hit = True
        elif stage not in ALLOWED_STAGES:
            report.fail(check, f"{fid}: invalid release_stage '{stage}'"); hit = True
        if not groundwork.strip():
            report.fail(check, f"{fid}: groundwork_required_now is empty"); hit = True
        elif groundwork not in ALLOWED_GROUNDWORK:
            report.fail(check, f"{fid}: invalid groundwork_required_now '{groundwork}'"); hit = True
        if safety and safety not in ALLOWED_SAFETY:
            report.fail(check, f"{fid}: invalid safety_classification '{safety}'"); hit = True
        for e in editions:
            if e not in ALLOWED_EDITIONS:
                report.fail(check, f"{fid}: invalid edition_availability entry '{e}'"); hit = True
        for p in platforms:
            if p not in ALLOWED_PLATFORMS:
                report.fail(check, f"{fid}: invalid platform_availability entry '{p}'"); hit = True
    if not hit:
        report.ok(check, f"checked implementation_status/release_stage/groundwork/safety/edition/platform values for {len(rows)} rows")


def check_ownership(report: Report, rows) -> None:
    check = "single-primary-owner"
    hit = False
    for row in rows:
        fid = row.get("feature_id", "?")
        owner = row.get("owner_volume", "").strip()
        if not owner:
            report.fail(check, f"{fid}: owner_volume is empty (every feature must have exactly one primary owner)"); hit = True
            continue
        if ";" in owner or "," in owner:
            report.fail(check, f"{fid}: owner_volume '{owner}' names more than one volume -- exactly one primary owner is required"); hit = True
            continue
        if not VOLUME_RE.fullmatch(owner):
            report.fail(check, f"{fid}: owner_volume '{owner}' is not a fully-resolvable DS-001..DS-023 volume reference"); hit = True
    if not hit:
        report.ok(check, f"every one of {len(rows)} features has exactly one resolvable primary owner_volume")


def check_supporting_volumes(report: Report, rows) -> None:
    check = "supporting-volumes-valid"
    hit = False
    for row in rows:
        fid = row.get("feature_id", "?")
        owner = row.get("owner_volume", "").strip()
        supporting = [v.strip() for v in row.get("supporting_volumes", "").split(";") if v.strip()]
        seen = set()
        for v in supporting:
            if v not in VALID_VOLUMES:
                report.fail(check, f"{fid}: supporting_volumes entry '{v}' is not a valid DS-001..DS-023 volume"); hit = True
            if v in seen:
                report.fail(check, f"{fid}: supporting_volumes contains duplicate entry '{v}'"); hit = True
            seen.add(v)
        if owner and owner in supporting:
            report.fail(check, f"{fid}: owner_volume '{owner}' is redundantly repeated in supporting_volumes"); hit = True
    if not hit:
        report.ok(check, f"supporting_volumes valid, deduplicated, and non-redundant with owner_volume for {len(rows)} rows")


def check_founder_customer_separation(report: Report, rows) -> None:
    check = "founder-customer-edition-separation"
    hit = False
    for row in rows:
        fid = row.get("feature_id", "?")
        editions = [e.strip() for e in row.get("edition_availability", "").split(";") if e.strip()]
        if editions == ["Founder"]:
            plats = [p.strip() for p in row.get("platform_availability", "").split(";") if p.strip()]
            if any(p in ("Web", "iOS", "Android") for p in plats) and fid in FOUNDER_DESKTOP_ONLY_FEATURES:
                report.fail(check, f"{fid}: Founder-only desktop capability lists a customer-reachable client platform {plats} in platform_availability"); hit = True
    if not hit:
        report.ok(check, "no Founder-only feature is misrepresented as a web/iOS/Android runtime")


def check_explicit_rejection(report: Report, rows) -> None:
    check = "explicitly-rejected-not-active"
    hit = False
    for row in rows:
        fid = row.get("feature_id", "?")
        status = row.get("implementation_status", "")
        if row.get("groundwork_required_now") == "Explicitly Rejected" and status in ACTIVE_STATUSES:
            report.fail(check, f"{fid}: groundwork_required_now=Explicitly Rejected but implementation_status={status!r} -- a rejected capability cannot carry an active status (must be Deprecated/Removed)"); hit = True
    if not hit:
        report.ok(check, "no explicitly-rejected feature carries an active implementation_status")


def check_evidence_discipline(report: Report, rows) -> None:
    check = "status-evidence-discipline"
    hit = False
    path_token_re = re.compile(r"[\w./\\-]+\.\w+|(?:backend|tests|shared|scripts|docs)[\w/\\-]*")
    for row in rows:
        fid = row.get("feature_id", "?")
        status = row.get("implementation_status", "")
        impl_ev = row.get("implementation_evidence", "").strip()
        test_ev = row.get("test_evidence", "").strip()
        release_ev = row.get("release_evidence", "").strip()
        blocker = row.get("blocker", "").strip()
        deprecation = row.get("deprecation_notes", "").strip()
        replacement = row.get("replacement_feature", "").strip()

        def _empty(v: str) -> bool:
            return (not v) or v.lower() == "none" or v.lower().startswith("none --") or v.lower().startswith("none -")

        if status == "Released":
            if _empty(impl_ev):
                report.fail(check, f"{fid}: status=Released but implementation_evidence is empty/None"); hit = True
            if _empty(test_ev):
                report.fail(check, f"{fid}: status=Released but test_evidence is empty/None"); hit = True
            if _empty(release_ev):
                report.fail(check, f"{fid}: status=Released but release_evidence is empty/None"); hit = True
        elif status == "Tested":
            if _empty(impl_ev):
                report.fail(check, f"{fid}: status=Tested but implementation_evidence is empty/None"); hit = True
            if _empty(test_ev):
                report.fail(check, f"{fid}: status=Tested but test_evidence is empty/None"); hit = True
        elif status == "Implemented":
            if _empty(impl_ev):
                report.fail(check, f"{fid}: status=Implemented but implementation_evidence is empty/None"); hit = True
        elif status == "Blocked":
            if _empty(blocker):
                report.fail(check, f"{fid}: status=Blocked but blocker is empty/None -- a specific obstacle must be named"); hit = True
        elif status == "Deprecated":
            if not deprecation:
                report.fail(check, f"{fid}: status={status} but deprecation_notes is empty"); hit = True
            elif not replacement and "no replacement" not in deprecation.lower() and "never implemented" not in deprecation.lower() and "explicitly rejected" not in deprecation.lower():
                report.warn(check, f"{fid}: status={status} has no replacement_feature and deprecation_notes does not explicitly state there is none")
        elif status == "Removed":
            # Removed requires removal evidence (release_evidence is repurposed as
            # the "how/when this was removed" field -- Removed and Released are
            # mutually exclusive statuses, so the field is otherwise unused here)
            # AND migration/cleanup/disposition evidence, not just a generic note.
            if _empty(release_ev):
                report.fail(check, f"{fid}: status=Removed but release_evidence (removal evidence) is empty/None"); hit = True
            if not deprecation:
                report.fail(check, f"{fid}: status=Removed but deprecation_notes is empty"); hit = True
            else:
                disposition_markers = ("migrat", "disposition", "no user data", "no dependent feature", "never implemented", "explicitly rejected")
                has_disposition = replacement.strip() != "" or any(m in deprecation.lower() for m in disposition_markers)
                if not has_disposition:
                    report.fail(check, f"{fid}: status=Removed but deprecation_notes states no migration/cleanup/disposition and no replacement_feature is set -- a generic deprecation note alone is not sufficient"); hit = True

        if status in ("Implemented", "Tested", "Released"):
            for field_name, value in (("implementation_evidence", impl_ev), ("test_evidence", test_ev)):
                if _empty(value):
                    continue
                for token in path_token_re.findall(value):
                    token = token.strip().rstrip(".,;")
                    if not token or "/" not in token.replace("\\", "/"):
                        continue
                    try:
                        p = resolve_repo_path(token)
                    except PathContainmentError:
                        continue
                    if not p.exists():
                        report.fail(check, f"{fid}: {field_name} references path '{token}' which does not exist in the repository"); hit = True
    if not hit:
        report.ok(check, "evidence fields are consistent with each row's declared implementation_status, and cited paths exist")


def check_self_referential_design_evidence(report: Report, rows) -> None:
    check = "no-self-referential-design-evidence"
    hit = False
    for row in rows:
        fid = row.get("feature_id", "?")
        if "this registry entry" in row.get("design_evidence", "").lower():
            report.fail(check, f"{fid}: design_evidence is self-referential ('This registry entry...') -- not accepted as real design evidence"); hit = True
    if not hit:
        report.ok(check, "no row cites its own registry entry as design evidence")


DESIGN_EVIDENCE_PLACEHOLDERS = {
    "", "none", "n/a", "not yet designed", "tbd",
    "tbd -- requirement not yet fully drafted",
    "this registry entry", "this registry entry (product expansion foundation pass)",
}


def check_designed_evidence(report: Report, rows) -> None:
    """implementation_status = Designed requires real design_evidence: a
    citation to an actual document/section, ADR, or controlled requirement.
    Empty/None/N/A/'Not Yet Designed'/'This registry entry'/other recognized
    placeholders are rejected. No code/test evidence is required for
    Designed (that is Implemented/Tested's job)."""
    check = "designed-status-requires-real-design-evidence"
    hit = False
    for row in rows:
        if row.get("implementation_status", "") != "Designed":
            continue
        fid = row.get("feature_id", "?")
        evidence = row.get("design_evidence", "").strip()
        normalized = evidence.lower()
        is_placeholder = (
            normalized in DESIGN_EVIDENCE_PLACEHOLDERS
            or "this registry entry" in normalized
            or normalized.startswith("tbd")
            or normalized.startswith("not yet designed")
        )
        if is_placeholder:
            report.fail(check, f"{fid}: implementation_status=Designed but design_evidence={evidence!r} is empty/placeholder, not real design evidence"); hit = True
    if not hit:
        report.ok(check, "every Designed feature carries real (non-placeholder) design_evidence")


def check_placeholder_acceptance(report: Report, rows) -> None:
    check = "no-placeholder-acceptance-on-committed-or-safety-critical"
    hit = False
    for row in rows:
        fid = row.get("feature_id", "?")
        acc = row.get("acceptance_summary", "")
        if "TBD" not in acc and acc.strip() != "":
            continue
        status = row.get("implementation_status", "")
        irr = row.get("initial_release_required", "").strip()
        safety = row.get("safety_classification", "").strip()
        permitted = (status in ("Idea", "Future")) and irr == "No" and (safety in NON_AUTHORITATIVE_SAFETY)
        if not permitted:
            report.fail(check, f"{fid}: placeholder acceptance_summary not permitted (status={status!r}, initial_release_required={irr!r}, safety_classification={safety!r}) -- see FEATURE_GOVERNANCE.md Section 3a"); hit = True
    if not hit:
        report.ok(check, "every placeholder acceptance_summary is governance-permitted (distant Idea/Future backlog, not initial-release-required, not safety-critical)")


def check_initial_release_status(report: Report, rows) -> None:
    check = "initial-release-required-not-idea-or-future"
    hit = False
    for row in rows:
        fid = row.get("feature_id", "?")
        status = row.get("implementation_status")
        if row.get("initial_release_required", "").strip() != "Yes":
            continue
        if status == "Idea":
            report.fail(check, f"{fid}: initial_release_required=Yes but implementation_status=Idea -- must be Planned or further along"); hit = True
        elif status == "Future":
            blocker = row.get("blocker", "").strip()
            deprecation = row.get("deprecation_notes", "").strip()
            if (not blocker or blocker.lower() == "none") and not deprecation:
                report.fail(check, f"{fid}: initial_release_required=Yes and implementation_status=Future with no blocker/explanation"); hit = True
    if not hit:
        report.ok(check, "no initial-release-required feature is silently Idea or unexplained Future")


def check_exit_management_safety(report: Report, rows) -> None:
    check = "exit-management-safety-classification"
    hit = False
    for row in rows:
        cat = row.get("category", "")
        if cat in (EXIT_MANAGEMENT_CATEGORY, ORDER_EXECUTION_CATEGORY):
            fid = row.get("feature_id", "?")
            safety = row.get("safety_classification", "")
            if safety not in ("Deterministic-Authoritative", "Informational"):
                report.fail(check, f"{fid} (category {cat!r}): safety_classification is {safety!r}, expected Deterministic-Authoritative or Informational"); hit = True
    if not hit:
        report.ok(check, "every Stop Loss/Take Profit and Order Management/Execution feature carries an explicit, expected safety_classification")


def check_exit_ds023_dependency(report: Report, rows) -> None:
    check = "exit-management-ds023-dependency"
    hit = False
    by_id = {r["feature_id"]: r for r in rows}
    for fid in REQUIRES_DS023:
        r = by_id.get(fid)
        if r is None:
            continue  # not every fixture/registry snapshot contains every known production ID
        supporting = r.get("supporting_volumes", "")
        deps = r.get("dependencies", "")
        owner = r.get("owner_volume", "").strip()
        if owner != "DS-023" and "DS-023" not in supporting and "DS-023" not in deps:
            report.fail(check, f"{fid}: order-lifecycle/reconciliation/failure-handling feature is missing a DS-023 dependency/supporting-volume (and is not itself DS-023-owned)"); hit = True
    for fid in REQUIRES_DS016_OR_DS022:
        r = by_id.get(fid)
        if r is None:
            continue
        supporting = r.get("supporting_volumes", "")
        if "DS-016" not in supporting and "DS-022" not in supporting:
            report.fail(check, f"{fid}: mobile/platform-specific exit-interaction feature is missing a DS-016 or DS-022 dependency"); hit = True
    if not hit:
        report.ok(check, "known order-lifecycle/mobile-interaction exit-management features carry the expected DS-023/DS-016/DS-022 dependencies")


def check_dependencies(report: Report, ids: set, rows):
    """Dependency edges must resolve, AND the registry's own `dependencies`
    column must be a normalized summary of the canonical FEATURE_DEPENDENCIES.csv
    edge file (never independently hand-edited), so the two can never drift.
    Returns the loaded dependency edge rows (or None) so callers can reuse
    them for cycle detection without re-reading the file."""
    check = "dependency-references-resolve"
    dep_rows = _load_csv(report, DEPENDENCIES_PATH, check)
    if dep_rows is None:
        return None
    unresolved = 0
    for row in dep_rows:
        for col in ("feature_id", "depends_on_feature_id"):
            fid = row.get(col, "")
            if fid not in ids:
                report.fail(check, f"{DEPENDENCIES_PATH}: '{col}'={fid!r} does not resolve to a real feature_id in {REGISTRY_PATH}")
                unresolved += 1
    if unresolved == 0:
        report.ok(check, f"all {len(dep_rows)} dependency edges resolve to real feature_id values")

    sync_check = "registry-dependencies-column-synchronized"
    expected: dict = {}
    for row in dep_rows:
        expected.setdefault(row["feature_id"], []).append(row["depends_on_feature_id"])
    hit = False
    for r in rows:
        fid = r["feature_id"]
        want = ";".join(expected.get(fid, []))
        got = r.get("dependencies", "")
        if want != got:
            report.fail(sync_check, f"{fid}: registry dependencies column {got!r} does not match FEATURE_DEPENDENCIES.csv-derived summary {want!r}"); hit = True
    if not hit:
        report.ok(sync_check, f"registry `dependencies` column matches {DEPENDENCIES_PATH} for all {len(rows)} rows")
    return dep_rows


def check_dependency_cycles(report: Report, dep_rows) -> None:
    """Deterministic directed-graph cycle detection over the canonical
    FEATURE_DEPENDENCIES.csv edges (feature_id -> depends_on_feature_id).
    Detects direct self-dependencies, two-node cycles, and longer cycles;
    reports the exact cycle path and the affected feature IDs. Iterates
    nodes/edges in the file's own order for determinism -- no feature IDs
    or totals are hard-coded."""
    check = "dependency-graph-acyclic"
    if not dep_rows:
        report.ok(check, "no dependency edges to check for cycles")
        return

    adjacency: dict = {}
    node_order: list = []
    for row in dep_rows:
        src = row["feature_id"]
        dst = row["depends_on_feature_id"]
        if src not in adjacency:
            adjacency[src] = []
            node_order.append(src)
        adjacency[src].append(dst)
        if dst not in adjacency:
            adjacency[dst] = []
            node_order.append(dst)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in node_order}
    reported_cycles = set()
    hit = False

    def _visit(start: str) -> None:
        nonlocal hit
        stack = [(start, iter(adjacency.get(start, [])))]
        path = [start]
        color[start] = GRAY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if color.get(nxt, WHITE) == GRAY:
                    # Found a back-edge -- extract the cycle portion of the path.
                    if nxt in path:
                        cycle_start = path.index(nxt)
                        cycle = path[cycle_start:] + [nxt]
                    else:
                        cycle = [node, nxt]
                    key = tuple(cycle)
                    if key not in reported_cycles:
                        reported_cycles.add(key)
                        arrow = " -> ".join(cycle)
                        affected = sorted(set(cycle))
                        report.fail(check, f"dependency cycle detected: {arrow} (affected feature IDs: {affected})")
                        hit = True
                elif color.get(nxt, WHITE) == WHITE:
                    color[nxt] = GRAY
                    path.append(nxt)
                    stack.append((nxt, iter(adjacency.get(nxt, []))))
                    advanced = True
                    break
            if not advanced:
                stack.pop()
                path.pop()
                color[node] = BLACK

    for n in node_order:
        if color[n] == WHITE:
            _visit(n)

    if not hit:
        report.ok(check, f"dependency graph is acyclic across {len(node_order)} node(s) and {len(dep_rows)} edge(s)")


def check_matrix(report: Report, rows, matrix_path: str, columns: tuple, registry_field: str, check_prefix: str) -> None:
    exists_check = f"{check_prefix}-one-row-per-feature"
    mrows = _load_csv(report, matrix_path, exists_check)
    if mrows is None:
        return
    reg_ids = {r["feature_id"] for r in rows}
    counts: dict = {}
    for m in mrows:
        counts.setdefault(m["feature_id"], 0)
        counts[m["feature_id"]] += 1
    hit = False
    for fid, n in counts.items():
        if n > 1:
            report.fail(exists_check, f"{matrix_path}: feature_id {fid} appears {n} times (expected exactly 1)"); hit = True
    missing = reg_ids - set(counts)
    extra = set(counts) - reg_ids
    for fid in sorted(missing):
        report.fail(exists_check, f"{matrix_path}: feature_id {fid} from the registry has no row"); hit = True
    for fid in sorted(extra):
        report.fail(exists_check, f"{matrix_path}: feature_id {fid} does not resolve to a registry row"); hit = True
    if not hit:
        report.ok(exists_check, f"{matrix_path} has exactly one row per registry feature ({len(reg_ids)})")

    vocab_check = f"{check_prefix}-controlled-values"
    hit = False
    for m in mrows:
        for col in columns:
            v = m.get(col, "").strip()
            if v not in ("Yes", "No", "N/A"):
                report.fail(vocab_check, f"{matrix_path}: {m['feature_id']}.{col} = {v!r}, expected Yes/No/N/A"); hit = True
    if not hit:
        report.ok(vocab_check, f"{matrix_path} uses only Yes/No/N/A values")

    agree_check = f"{check_prefix}-agrees-with-registry"
    reg_by_id = {r["feature_id"]: r for r in rows}
    hit = False
    for m in mrows:
        fid = m["feature_id"]
        r = reg_by_id.get(fid)
        if r is None:
            continue
        reg_values = {v.strip() for v in r.get(registry_field, "").split(";") if v.strip()}
        if reg_values == {"N/A"} or not reg_values:
            # Not a platform/edition-bound feature: every matrix cell must be N/A too.
            non_na = {col for col in columns if m.get(col, "").strip() != "N/A"}
            if non_na:
                report.fail(agree_check, f"{fid}: registry {registry_field}=N/A but {matrix_path} has non-N/A cell(s) {sorted(non_na)}"); hit = True
            continue
        expected_yes = reg_values & set(columns)
        matrix_yes = {col for col in columns if m.get(col, "").strip() == "Yes"}
        matrix_na = {col for col in columns if m.get(col, "").strip() == "N/A"}
        if matrix_na:
            report.fail(agree_check, f"{fid}: registry {registry_field}={sorted(reg_values)} is platform/edition-bound but {matrix_path} has N/A cell(s) {sorted(matrix_na)}"); hit = True
        if matrix_yes != expected_yes:
            report.fail(agree_check, f"{fid}: {matrix_path} Yes-columns {sorted(matrix_yes)} disagree with registry {registry_field} {sorted(expected_yes)}"); hit = True
    if not hit:
        report.ok(agree_check, f"{matrix_path} agrees with registry `{registry_field}` for every resolvable feature")


def check_platform_edition_specific_rules(report: Report) -> None:
    check = "founder-only-not-customer-enabled-matrix"
    prows = _load_csv(report, PLATFORM_MATRIX_PATH, check)
    hit = False
    if prows is not None:
        by_id = {p["feature_id"]: p for p in prows}
        for fid in FOUNDER_DESKTOP_ONLY_FEATURES:
            p = by_id.get(fid)
            if p is None:
                continue  # not every fixture/registry snapshot contains every known production ID
            for client in ("Web", "iOS", "Android"):
                if p.get(client, "").strip() == "Yes":
                    report.fail(check, f"{fid}: {PLATFORM_MATRIX_PATH} marks {client}=Yes for a Founder desktop/workstation-only capability"); hit = True
    if not hit:
        report.ok(check, "Founder desktop/workstation-only capabilities are not marked available on Web/iOS/Android")


def check_tradingview(report: Report, ids: set, rows) -> dict:
    check = "tradingview-feature-id-references-resolve"
    try:
        path = resolve_repo_path(TRADINGVIEW_PATH)
    except PathContainmentError as exc:
        report.fail(check, str(exc))
        return {}
    if not path.is_file():
        report.warn(check, f"{TRADINGVIEW_PATH} does not exist -- skipping")
        return {}
    text = path.read_text(encoding="utf-8")
    unresolved = 0
    resolved = 0
    for m in TV_ID_RE.finditer(text):
        fid = m.group(0)
        if fid in ids:
            resolved += 1
        else:
            unresolved += 1
            line_no = text.count("\n", 0, m.start()) + 1
            report.fail(check, f"{TRADINGVIEW_PATH}:{line_no}: '{fid}' does not resolve to a real feature_id")
    if unresolved == 0:
        report.ok(check, f"all {resolved} feature_id references in {TRADINGVIEW_PATH} resolve")

    class_check = "tradingview-classification-agrees-with-registry"
    reg_by_id = {r["feature_id"]: r for r in rows}
    counts: dict = {}
    hit = False
    for m in TV_ROW_RE.finditer(text):
        _cap, cls, fid, _note = m.groups()
        counts[cls] = counts.get(cls, 0) + 1
        r = reg_by_id.get(fid)
        if r is None:
            continue
        irr = r.get("initial_release_required", "").strip()
        stage = r.get("release_stage", "").strip()
        gw = r.get("groundwork_required_now", "").strip()
        status = r.get("implementation_status", "").strip()
        if irr == "Yes":
            expected = "A"
        elif gw == "Explicitly Rejected":
            expected = "E"
        elif stage == "Stage 3 -- Founder Workstation Beta":
            expected = "B"
        elif gw == "Groundwork Required Now":
            expected = "C"
        else:
            expected = "D"
        if cls != expected:
            report.fail(class_check, f"{fid}: TradingView class {cls!r} disagrees with registry-derived expectation {expected!r} (initial_release_required={irr!r}, release_stage={stage!r}, groundwork_required_now={gw!r})"); hit = True
        if cls == "E" and status in ACTIVE_STATUSES - {"Idea"}:
            report.fail(class_check, f"{fid}: TradingView class E (explicitly rejected) but implementation_status={status!r}"); hit = True
        if cls == "D" and gw == "Groundwork Required Now":
            report.fail(class_check, f"{fid}: TradingView class D (long-term backlog) but groundwork_required_now=Groundwork Required Now with no documented exception"); hit = True
    if not hit:
        report.ok(class_check, "every classified TradingView row agrees with its registry-derived expected class")
    return counts


def run_all() -> Report:
    report = Report()
    rows = _load_registry(report)
    if rows is None:
        return report
    check_schema(report, rows)
    ids = check_unique_ids(report, rows)
    check_malformed_ids(report, ids)
    check_controlled_vocabularies(report, rows)
    check_ownership(report, rows)
    check_supporting_volumes(report, rows)
    check_founder_customer_separation(report, rows)
    check_explicit_rejection(report, rows)
    check_evidence_discipline(report, rows)
    check_self_referential_design_evidence(report, rows)
    check_designed_evidence(report, rows)
    check_placeholder_acceptance(report, rows)
    check_initial_release_status(report, rows)
    check_exit_management_safety(report, rows)
    check_exit_ds023_dependency(report, rows)
    dep_rows = check_dependencies(report, ids, rows)
    check_dependency_cycles(report, dep_rows)
    check_matrix(report, rows, PLATFORM_MATRIX_PATH, CLIENT_PLATFORMS, "platform_availability", "platform-matrix")
    check_matrix(report, rows, EDITION_MATRIX_PATH, ("Founder", "Customer"), "edition_availability", "edition-matrix")
    check_platform_edition_specific_rules(report)
    tv_counts = check_tradingview(report, ids, rows)
    if tv_counts:
        report.ok("tradingview-totals", f"A={tv_counts.get('A',0)} B={tv_counts.get('B',0)} C={tv_counts.get('C',0)} D={tv_counts.get('D',0)} E={tv_counts.get('E',0)}")
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
