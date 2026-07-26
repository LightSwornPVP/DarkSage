#!/usr/bin/env python3
"""Validate the DarkSage launch readiness artifacts in docs/launch.

Beyond schema/format checks, this validator enforces the substance of
launch readiness: Founder Alpha -> Founder Beta -> Customer Beta gate
progression, Commercial Release Readiness's dependency on billing/legal/
support/communications/rollback/Customer-Beta/Live-Trading-Pilot readiness,
explicit live-trading-pilot evidence categories, required transactional
email purposes (including Automation Halted / Critical Incident), billing
scenarios that preserve read-only historical/export access on cancellation,
grace-period expiration, suspension, and chargeback, analytics property
minimization, legal-register truthfulness, and real content checks against
the support/rollback/launch-day runbooks.

Standard library only. No network access. Exits 0 only if no FAIL-level
finding was produced.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from _repo import PathContainmentError, resolve_repo_path

LAUNCH_MATRIX = "docs/launch/LAUNCH_GATE_MATRIX.csv"
TRANSACTIONAL_EMAIL_REGISTER = "docs/launch/TRANSACTIONAL_EMAIL_REGISTER.csv"
BILLING_TEST_MATRIX = "docs/launch/BILLING_TEST_MATRIX.csv"
LEGAL_ARTIFACT_REGISTER = "docs/launch/LEGAL_AND_POLICY_ARTIFACT_REGISTER.csv"
PRODUCT_ANALYTICS_EVENT_REGISTER = "docs/launch/PRODUCT_ANALYTICS_EVENT_REGISTER.csv"
SUPPORT_OPERATIONS_PLAN = "docs/launch/SUPPORT_OPERATIONS_PLAN.md"
RELEASE_ROLLBACK_RUNBOOK = "docs/launch/RELEASE_ROLLBACK_RUNBOOK.md"
LAUNCH_DAY_RUNBOOK = "docs/launch/LAUNCH_DAY_RUNBOOK.md"

ALLOWED_STATES = {"Planned", "In Progress", "Complete", "Implemented", "Tested", "Blocked", "Deferred"}
ALLOWED_RELEASE_STAGES = {
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
ALLOWED_GATES = {
    "Founder Alpha Readiness",
    "Founder Beta Readiness",
    "Customer Beta Readiness",
    "Live-Trading Pilot Readiness",
    "Commercial Release Readiness",
    "Launch-Day Go/No-Go",
    "Post-Launch Stabilization Exit",
}
ALLOWED_SEVERITIES = {"Low", "Medium", "High", "Critical"}
ALLOWED_IMPACTS = {"Low", "Medium", "High", "Critical", "Very High", "Founder-only"}

# Case-insensitive: the register spells these "Automation halted" / "Critical
# incident", so comparisons are done in lowercase throughout this module.
REQUIRED_TRANSACTIONAL_EMAIL_PURPOSES = {
    "email verification", "password reset", "new-device login", "security alert",
    "mfa recovery", "subscription confirmation", "payment receipt", "failed payment",
    "trial ending", "grace period started", "grace period ending",
    "cancellation confirmation", "support-case update", "policy update notice",
    "broker disconnected", "data export ready", "account deletion confirmation",
    "automation halted", "critical incident",
}

REQUIRED_BILLING_SCENARIO_EVENTS = {
    "Successful payment", "Card declined", "Expired card", "Insufficient funds",
    "Duplicate webhook", "Delayed webhook", "Missing webhook", "Replayed webhook",
    "Upgrade", "Downgrade", "Proration", "Subscription cancelled", "Refund issued",
    "Partial refund", "Chargeback detected", "Failed renewal", "Grace-period start",
    "Grace-period expiration", "Subscription restoration", "Tax calculation",
    "Invoice generation", "Receipt generation", "Regional sales restriction",
    "Account suspension", "Data-access behavior after cancellation",
}

# Billing events that terminate or suspend active paid access. None of these
# may read as removing read-only historical/export access entirely.
HISTORICAL_ACCESS_EVENTS = {
    "Subscription cancelled",
    "Grace-period expiration",
    "Account suspension",
    "Chargeback detected",
    "Data-access behavior after cancellation",
}

REQUIRED_ANALYTICS_EVENTS = {
    "landing_page_viewed", "waitlist_joined", "account_created", "email_verified",
    "onboarding_started", "onboarding_completed", "risk_profile_completed",
    "paper_broker_connected", "first_watchlist_created", "first_screener_run",
    "first_trade_intelligence_package_viewed", "first_paper_trade_proposed",
    "first_paper_trade_approved", "first_paper_trade_rejected", "first_exit_plan_created",
    "first_stop_loss_created", "first_take_profit_target_created",
    "first_journal_entry_completed", "first_morning_brief_viewed",
    "first_needs_my_attention_resolved", "trial_started", "subscription_started",
    "payment_failed", "subscription_cancelled", "data_export_requested",
    "account_deletion_requested", "user_returned_after_7_days",
    "user_returned_after_30_days", "user_returned_after_90_days",
}

# Matched as a whole underscore-delimited token or component (e.g. both
# "profile_summary" and "user_profile_summary_v2" are rejected), never as a
# bare substring of an unrelated identifier (e.g. "risk_profile_completed"
# must NOT trip on "profile").
PROHIBITED_ANALYTICS_TERMS = [
    "profile_summary", "risk_profile_contents", "broker_credentials", "broker_token",
    "order_payload", "journal_content", "prompt_content", "account_value",
    "card_number", "secret", "password", "access_token",
]

REQUIRED_LEGAL_ARTIFACTS = {
    "Terms of Service", "Privacy Policy", "Cookie Policy", "Acceptable Use Policy",
    "Subscription Terms", "Refund Policy", "Financial-Risk Disclosure",
    "Automated Trading Consent", "Broker-Linking Consent", "Vulnerability Disclosure Policy",
}

LIVE_TRADING_EVIDENCE_CATEGORIES: dict[str, list[str]] = {
    "deterministic validation pipeline": [r"deterministic validation pipeline"],
    "broker certification": [r"broker.{0,25}certificat"],
    "order idempotency": [r"idempotenc"],
    "duplicate prevention": [r"duplicate prevention", r"duplicate.{0,20}(order|submission)"],
    "reconciliation": [r"reconcil"],
    "partial-fill handling": [r"partial-fill"],
    "stale/unknown order handling": [r"stale order", r"unknown order"],
    "kill switches": [r"kill switch"],
    "exits-only mode": [r"exits-only"],
    "stop-loss/take-profit protection": [r"stop-loss.{0,10}take-profit"],
    "broker-state monitoring": [r"broker-state monitoring", r"broker state monitoring"],
    "security review": [r"security review"],
    "live unlock approval": [r"live unlock approval"],
    "rollback readiness": [r"rollback"],
    "incident response": [r"incident-response", r"incident response"],
    "customer consent": [r"customer consent"],
    "audit logging": [r"audit logging"],
}

SUPPORT_PLAN_CATEGORIES: dict[str, list[str]] = {
    "severity levels": [r"severity level"],
    "response targets": [r"response target"],
    "escalation": [r"escalation"],
    "decision authority": [r"decision authority"],
    "diagnostics with consent": [r"diagnostic.{0,40}consent", r"consent.{0,40}diagnostic"],
    "customer communication": [r"communication"],
    "evidence capture": [r"evidence"],
    "closure criteria": [r"closure"],
    "post-incident review": [r"post-incident review"],
}

ROLLBACK_RUNBOOK_CATEGORIES: dict[str, list[str]] = {
    "fail-closed unknown-order handling": [r"fail-closed"],
    "broker reconciliation": [r"reconcil"],
    "duplicate prevention": [r"duplicate"],
    "partial-fill handling": [r"partial fill"],
    "stale acknowledgement handling": [r"stale.{0,40}acknowledg", r"acknowledg.{0,40}stale"],
    "exits-only mode": [r"exits-only"],
    "automation suspension": [r"automation (halt|suspend)"],
    "kill switch": [r"kill switch"],
    "customer communication": [r"notify.{0,25}customer", r"customer communication"],
    "incident escalation": [r"escalat"],
    "post-rollback validation": [r"post-rollback"],
    "state ownership": [r"ownership", r"owns the recovered state"],
}

LAUNCH_DAY_RUNBOOK_CATEGORIES: dict[str, list[str]] = {
    "ordered steps": [r"(?m)^\d+\.\s"],
    "roles": [r"role"],
    "go/no-go criteria": [r"go/no-go"],
    "stop conditions": [r"stop condition"],
    "monitoring thresholds": [r"monitoring.{0,80}threshold", r"threshold.{0,80}monitoring"],
    "evidence capture": [r"evidence"],
    "rollback triggers": [r"rollback.{0,40}(trigger|issue|condition)"],
    "sign-off": [r"signs?\s*-?\s*off"],
}


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


def _resolve_csv(path: str) -> Optional[Path]:
    p = resolve_repo_path(path)
    return p if p.is_file() else None


def _is_safe_path(value: str) -> bool:
    if not value or not value.strip():
        return False
    if value.startswith("/") or value.startswith("\\"):
        return False
    if ".." in value:
        return False
    return True


def _read_csv(path: str) -> list[dict[str, str]]:
    p = resolve_repo_path(path)
    with p.open("r", encoding="utf-8", newline="") as f:
        return [row for row in csv.DictReader(f)]


def _row_by_name(rows: list[dict[str, str]], name: str) -> Optional[dict[str, str]]:
    for row in rows:
        if row.get("name", "").strip() == name:
            return row
    return None


def _row_by_id(rows: list[dict[str, str]], item_id: str) -> Optional[dict[str, str]]:
    for row in rows:
        if row.get("launch_item_id", "").strip() == item_id:
            return row
    return None


def _dep_ids(row: dict[str, str]) -> set[str]:
    return {d.strip() for d in row.get("dependency_items", "").split(";") if d.strip()}


def _read_doc_text(path: str) -> Optional[str]:
    p = resolve_repo_path(path)
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def check_launch_item_schema(report: Report) -> list[dict[str, str]]:
    check = "launch-item-schema"
    path = resolve_repo_path(LAUNCH_MATRIX)
    if not path.is_file():
        report.fail(check, f"{LAUNCH_MATRIX} does not exist")
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        required = [
            "launch_item_id", "name", "description", "category", "owner_volume",
            "supporting_volumes", "release_stage", "applicable_gate", "blocking_severity",
            "implementation_status", "evidence_required", "evidence_location",
            "verification_method", "approver_role", "last_verified_date", "dependency_items",
            "rollback_required", "customer_impact", "security_impact", "legal_review_required", "notes",
        ]
        missing = [col for col in required if col not in header]
        if missing:
            report.fail(check, f"{LAUNCH_MATRIX} missing columns: {missing}")
            return []
        rows = [row for row in reader]
        if not rows:
            report.fail(check, f"{LAUNCH_MATRIX} contains no rows")
        else:
            report.ok(check, f"{LAUNCH_MATRIX} contains {len(rows)} row(s) with all {len(required)} required columns")
        return rows


def check_unique_launch_ids(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-item-id-uniqueness"
    seen: dict[str, int] = {}
    dup = False
    for i, row in enumerate(rows):
        item_id = row.get("launch_item_id", "").strip()
        if not item_id:
            report.fail(check, f"row {i+2} has empty launch_item_id")
            continue
        if item_id in seen:
            report.fail(check, f"duplicate launch_item_id: {item_id}")
            dup = True
        seen[item_id] = i + 2
    if not dup:
        report.ok(check, f"all {len(seen)} launch_item_id value(s) are unique")


def check_required_fields(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-required-fields"
    for i, row in enumerate(rows):
        for field_name in ["name", "category", "owner_volume", "release_stage", "applicable_gate", "implementation_status", "evidence_required"]:
            if not row.get(field_name, "").strip():
                report.fail(check, f"row {i+2} missing required field: {field_name}")


def check_evidence_locations(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-evidence-locations"
    for i, row in enumerate(rows):
        location = row.get("evidence_location", "").strip()
        if not location:
            report.fail(check, f"row {i+2} missing evidence_location")
            continue
        if not _is_safe_path(location):
            report.fail(check, f"row {i+2} has unsafe evidence_location: {location}")
            continue
        try:
            resolved = resolve_repo_path(location)
        except PathContainmentError:
            report.fail(check, f"row {i+2} has path traversal in evidence_location: {location}")
            continue
        if not resolved.exists():
            report.fail(check, f"row {i+2} evidence_location does not exist: {location}")


def check_owner_volume_format(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-owner-volume-format"
    for i, row in enumerate(rows):
        owner = row.get("owner_volume", "").strip()
        if owner and not owner.startswith("DS-"):
            report.fail(check, f"row {i+2} has invalid owner_volume: {owner}")


def check_release_stage_and_gate(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-gate-values"
    for i, row in enumerate(rows):
        gate = row.get("applicable_gate", "").strip()
        if gate and gate not in ALLOWED_GATES:
            report.fail(check, f"row {i+2} has invalid applicable_gate: {gate}")
        status = row.get("implementation_status", "").strip()
        if status and status not in ALLOWED_STATES:
            report.fail(check, f"row {i+2} has invalid implementation_status: {status}")
        stage = row.get("release_stage", "").strip()
        if stage and stage not in ALLOWED_RELEASE_STAGES:
            report.fail(check, f"row {i+2} has invalid release_stage: {stage}")


def check_severity_and_impact_values(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-severity-impact-values"
    for i, row in enumerate(rows):
        severity = row.get("blocking_severity", "").strip()
        if severity and severity not in ALLOWED_SEVERITIES:
            report.fail(check, f"row {i+2} has invalid blocking_severity: {severity}")
        for field_name in ("customer_impact", "security_impact"):
            value = row.get(field_name, "").strip()
            if value and value not in ALLOWED_IMPACTS:
                report.fail(check, f"row {i+2} has invalid {field_name}: {value}")


def check_dependency_items(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-dependency-items"
    ids = {row.get("launch_item_id", "").strip() for row in rows if row.get("launch_item_id", "").strip()}
    for i, row in enumerate(rows):
        for dep in _dep_ids(row):
            if dep not in ids:
                report.fail(check, f"row {i+2} references unknown dependency_items: {dep}")


def check_launch_item_id_format(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-item-id-format"
    for i, row in enumerate(rows):
        item_id = row.get("launch_item_id", "").strip()
        if item_id and not re.fullmatch(r"LAUNCH-\d{4}", item_id):
            report.fail(check, f"row {i+2} has malformed launch_item_id: {item_id}")


def check_supporting_volumes(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-supporting-volumes"
    for i, row in enumerate(rows):
        owner = row.get("owner_volume", "").strip()
        if owner and not re.fullmatch(r"DS-\d{3}", owner):
            report.fail(check, f"row {i+2} has invalid owner_volume: {owner}")
        seen: set[str] = set()
        for component in [v.strip() for v in row.get("supporting_volumes", "").split(";") if v.strip()]:
            if not re.fullmatch(r"DS-\d{3}", component):
                report.fail(check, f"row {i+2} has invalid supporting_volumes entry: {component}")
            if component in seen:
                report.fail(check, f"row {i+2} has duplicate supporting_volumes entry: {component}")
            seen.add(component)
            if component == owner:
                report.fail(check, f"row {i+2} owner_volume duplicated in supporting_volumes: {component}")


def check_volume_numbers_in_range(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-volume-range"
    for i, row in enumerate(rows):
        candidates = [row.get("owner_volume", "").strip()]
        candidates += [v.strip() for v in row.get("supporting_volumes", "").split(";") if v.strip()]
        for vid in candidates:
            m = re.fullmatch(r"DS-(\d{3})", vid)
            if not m:
                continue
            num = int(m.group(1))
            if not (1 <= num <= 23):
                report.fail(check, f"row {i+2} references out-of-range volume: {vid}")


def check_launch_dependency_cycles(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-dependency-cycles"
    ids = [row.get("launch_item_id", "").strip() for row in rows if row.get("launch_item_id", "").strip()]
    adjacency: dict[str, list[str]] = {item_id: [] for item_id in ids}
    for row in rows:
        item_id = row.get("launch_item_id", "").strip()
        if not item_id:
            continue
        for dep in _dep_ids(row):
            if dep in adjacency:
                adjacency[item_id].append(dep)
    visited: dict[str, str] = {}
    stack: list[str] = []
    found_cycle = False

    def dfs(node: str) -> None:
        nonlocal found_cycle
        visited[node] = "GRAY"
        stack.append(node)
        for neighbor in adjacency.get(node, []):
            if visited.get(neighbor) == "GRAY":
                if neighbor in stack:
                    cycle = stack[stack.index(neighbor):] + [neighbor]
                    report.fail(check, f"dependency cycle detected: {' -> '.join(cycle)}")
                else:
                    report.fail(check, f"dependency cycle detected involving {node} and {neighbor}")
                found_cycle = True
                break
            if visited.get(neighbor) != "BLACK":
                dfs(neighbor)
        stack.pop()
        visited[node] = "BLACK"

    for item_id in ids:
        if visited.get(item_id) is None:
            dfs(item_id)
    if not found_cycle:
        report.ok(check, f"launch dependency graph is acyclic across {len(ids)} item(s)")


def check_evidence_required_values(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-evidence-required-values"
    for i, row in enumerate(rows):
        value = row.get("evidence_required", "").strip()
        if not value:
            report.fail(check, f"row {i+2} missing evidence_required")
        elif value not in {"Yes", "No"}:
            report.fail(check, f"row {i+2} has invalid evidence_required: {value}")


def check_rollback_required(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-rollback-required"
    for i, row in enumerate(rows):
        value = row.get("rollback_required", "").strip()
        if not value:
            report.fail(check, f"row {i+2} missing rollback_required")
        elif value not in {"Yes", "No"}:
            report.fail(check, f"row {i+2} has invalid rollback_required: {value}")


def check_legal_review_required(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-legal-review"
    for i, row in enumerate(rows):
        if row.get("legal_review_required", "").strip().lower() == "yes" and not row.get("evidence_location", "").strip():
            report.fail(check, f"row {i+2} requires legal review evidence but has empty evidence_location")


def check_gate_complete_evidence(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-complete-gate-evidence"
    for i, row in enumerate(rows):
        status = row.get("implementation_status", "").strip()
        evidence = row.get("evidence_location", "").strip()
        if status in {"Complete", "Implemented", "Tested"} and not evidence:
            report.fail(check, f"row {i+2} is {status} but missing evidence_location")


# ---------------------------------------------------------------------------
# A. Gate progression and Commercial Release Readiness dependency substance
# ---------------------------------------------------------------------------


def check_gate_progression(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-gate-progression"
    alpha = _row_by_name(rows, "Founder Alpha Readiness")
    beta = _row_by_name(rows, "Founder Beta Readiness")
    cbeta = _row_by_name(rows, "Customer Beta Readiness")

    if not alpha:
        report.fail(check, "no launch item named 'Founder Alpha Readiness' was found")
    if not beta:
        report.fail(check, "no launch item named 'Founder Beta Readiness' was found")
    if not cbeta:
        report.fail(check, "no launch item named 'Customer Beta Readiness' was found")

    if alpha and beta:
        if alpha.get("launch_item_id", "").strip() not in _dep_ids(beta):
            report.fail(check, "Founder Beta Readiness does not depend on Founder Alpha Readiness (Alpha -> Beta progression is not enforced)")
        else:
            report.ok(check, "Founder Beta Readiness depends on Founder Alpha Readiness")

    if beta and cbeta:
        if beta.get("launch_item_id", "").strip() not in _dep_ids(cbeta):
            report.fail(check, "Customer Beta Readiness does not depend on Founder Beta Readiness (Beta -> Customer Beta progression is not enforced)")
        else:
            report.ok(check, "Customer Beta Readiness depends on Founder Beta Readiness")


COMMERCIAL_DEPENDENCY_KEYWORDS = {
    "billing readiness": "billing",
    "legal/policy readiness": "legal",
    "support operations": "support",
    "customer communications": "communication",
    "rollback readiness": "rollback",
}


def check_commercial_release_dependencies(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-commercial-release-dependencies"
    commercial = _row_by_name(rows, "Commercial Release Readiness")
    if not commercial:
        report.fail(check, "no launch item named 'Commercial Release Readiness' was found")
        return

    dep_ids = _dep_ids(commercial)
    dep_rows = [r for r in (_row_by_id(rows, d) for d in dep_ids) if r]
    dep_names_blob = " ; ".join(r.get("name", "") for r in dep_rows).lower()

    for label, keyword in COMMERCIAL_DEPENDENCY_KEYWORDS.items():
        if keyword not in dep_names_blob:
            report.fail(check, f"Commercial Release Readiness has no dependency covering {label} (expected a dependency item whose name mentions '{keyword}')")
        else:
            report.ok(check, f"Commercial Release Readiness depends on an item covering {label}")

    cbeta = _row_by_name(rows, "Customer Beta Readiness")
    if cbeta:
        if cbeta.get("launch_item_id", "").strip() not in dep_ids:
            report.fail(check, "Commercial Release Readiness does not depend on Customer Beta Readiness")
        else:
            report.ok(check, "Commercial Release Readiness depends on Customer Beta Readiness")

    live_row = _row_by_name(rows, "Live-Trading Pilot Readiness")
    if live_row is not None:
        if live_row.get("launch_item_id", "").strip() not in dep_ids:
            report.fail(check, "a Live-Trading Pilot Readiness item exists but Commercial Release Readiness does not depend on it")
        else:
            report.ok(check, "Commercial Release Readiness depends on Live-Trading Pilot Readiness")


# ---------------------------------------------------------------------------
# B. Live-Trading Pilot evidence categories
# ---------------------------------------------------------------------------


def check_live_trading_pilot_evidence(report: Report, rows: list[dict[str, str]]) -> None:
    check = "launch-live-trading-pilot-evidence"
    live_row = _row_by_name(rows, "Live-Trading Pilot Readiness")
    if live_row is None:
        report.warn(check, "no Live-Trading Pilot Readiness item found -- skipping evidence-category check")
        return
    evidence_location = live_row.get("evidence_location", "").strip()
    if not evidence_location or not _is_safe_path(evidence_location):
        report.fail(check, "Live-Trading Pilot Readiness evidence_location is missing or unsafe")
        return
    text = _read_doc_text(evidence_location)
    if text is None:
        report.fail(check, f"Live-Trading Pilot Readiness evidence_location does not exist: {evidence_location}")
        return
    missing = []
    for category, patterns in LIVE_TRADING_EVIDENCE_CATEGORIES.items():
        if not any(re.search(p, text, re.IGNORECASE) for p in patterns):
            missing.append(category)
    if missing:
        report.fail(check, f"{evidence_location} is missing required live-trading pilot evidence categor{'y' if len(missing)==1 else 'ies'}: {missing}")
    else:
        report.ok(check, f"{evidence_location} covers all {len(LIVE_TRADING_EVIDENCE_CATEGORIES)} required live-trading pilot evidence categories")


# ---------------------------------------------------------------------------
# C. Transactional emails
# ---------------------------------------------------------------------------


def check_required_transactional_emails(report: Report) -> None:
    check = "launch-transactional-emails"
    path = _resolve_csv(TRANSACTIONAL_EMAIL_REGISTER)
    if path is None:
        report.fail(check, f"{TRANSACTIONAL_EMAIL_REGISTER} does not exist")
        return
    rows = _read_csv(TRANSACTIONAL_EMAIL_REGISTER)
    found = {row.get("purpose", "").strip().lower() for row in rows}
    missing = sorted(p for p in REQUIRED_TRANSACTIONAL_EMAIL_PURPOSES if p not in found)
    if missing:
        report.fail(check, f"missing transactional email purpose(s): {missing}")
    else:
        report.ok(check, f"all {len(REQUIRED_TRANSACTIONAL_EMAIL_PURPOSES)} required transactional email purposes are present")


# ---------------------------------------------------------------------------
# D. Billing scenarios and historical-access preservation
# ---------------------------------------------------------------------------


def check_required_billing_scenarios(report: Report) -> None:
    check = "launch-billing-scenarios"
    path = _resolve_csv(BILLING_TEST_MATRIX)
    if path is None:
        report.fail(check, f"{BILLING_TEST_MATRIX} does not exist")
        return
    rows = _read_csv(BILLING_TEST_MATRIX)
    found = {row.get("event", "").strip() for row in rows}
    missing = sorted(e for e in REQUIRED_BILLING_SCENARIO_EVENTS if e not in found)
    if missing:
        report.fail(check, f"missing billing scenario event(s): {missing}")
    else:
        report.ok(check, f"all {len(REQUIRED_BILLING_SCENARIO_EVENTS)} required billing scenario events are present")


def check_billing_historical_access_preserved(report: Report) -> None:
    check = "launch-billing-historical-access"
    path = _resolve_csv(BILLING_TEST_MATRIX)
    if path is None:
        report.fail(check, f"{BILLING_TEST_MATRIX} does not exist")
        return
    rows = _read_csv(BILLING_TEST_MATRIX)
    matched = 0
    for row in rows:
        event = row.get("event", "").strip()
        if event not in HISTORICAL_ACCESS_EVENTS:
            continue
        matched += 1
        combined = " ".join([
            row.get("expected_billing_state", ""),
            row.get("expected_entitlement_state", ""),
            row.get("expected_customer_notification", ""),
            row.get("rollback_recovery_behavior", ""),
            row.get("notes", ""),
        ]).lower()
        has_readonly = "read-only" in combined or "read only" in combined
        has_retained_scope = "histor" in combined or "export" in combined
        if not (has_readonly and has_retained_scope):
            report.fail(
                check,
                f"{row.get('test_id')} ({event}) does not clearly preserve read-only historical/export access "
                f"after the active entitlement change",
            )
        else:
            report.ok(check, f"{row.get('test_id')} ({event}) preserves read-only historical/export access")
    if matched < len(HISTORICAL_ACCESS_EVENTS):
        found_events = {row.get("event", "").strip() for row in rows}
        missing_events = sorted(HISTORICAL_ACCESS_EVENTS - found_events)
        if missing_events:
            report.fail(check, f"billing test matrix has no row for historical-access-sensitive event(s): {missing_events}")


# ---------------------------------------------------------------------------
# E. Analytics property minimization
# ---------------------------------------------------------------------------


def check_required_analytics_events(report: Report) -> None:
    check = "launch-analytics-events"
    path = _resolve_csv(PRODUCT_ANALYTICS_EVENT_REGISTER)
    if path is None:
        report.fail(check, f"{PRODUCT_ANALYTICS_EVENT_REGISTER} does not exist")
        return
    rows = _read_csv(PRODUCT_ANALYTICS_EVENT_REGISTER)
    found = {row.get("event_name", "").strip() for row in rows}
    missing = sorted(e for e in REQUIRED_ANALYTICS_EVENTS if e not in found)
    if missing:
        report.fail(check, f"missing analytics event(s): {missing}")
    else:
        report.ok(check, f"all {len(REQUIRED_ANALYTICS_EVENTS)} required analytics events are present")


def check_analytics_property_minimization(report: Report) -> None:
    check = "launch-analytics-minimization"
    path = _resolve_csv(PRODUCT_ANALYTICS_EVENT_REGISTER)
    if path is None:
        return
    rows = _read_csv(PRODUCT_ANALYTICS_EVENT_REGISTER)
    hit = False
    for row in rows:
        props = [p.strip() for p in row.get("properties", "").split(";") if p.strip()]
        for prop in props:
            for term in PROHIBITED_ANALYTICS_TERMS:
                if re.search(rf"(?:^|_){re.escape(term)}(?:_|$)", prop, re.IGNORECASE):
                    report.fail(check, f"{row.get('event_name')}: property '{prop}' contains prohibited sensitive concept '{term}'")
                    hit = True
    if not hit:
        report.ok(check, f"no analytics event property matched a prohibited sensitive concept across {len(rows)} event(s)")


# ---------------------------------------------------------------------------
# F. Legal register truthfulness
# ---------------------------------------------------------------------------


def check_required_legal_artifacts(report: Report) -> None:
    check = "launch-legal-artifacts"
    path = _resolve_csv(LEGAL_ARTIFACT_REGISTER)
    if path is None:
        report.fail(check, f"{LEGAL_ARTIFACT_REGISTER} does not exist")
        return
    rows = _read_csv(LEGAL_ARTIFACT_REGISTER)
    found = {row.get("artifact_name", "").strip() for row in rows}
    missing = sorted(a for a in REQUIRED_LEGAL_ARTIFACTS if a not in found)
    if missing:
        report.fail(check, f"missing legal artifact(s): {missing}")
    else:
        report.ok(check, f"all {len(REQUIRED_LEGAL_ARTIFACTS)} required legal artifacts are present")


def check_legal_register_truthfulness(report: Report) -> None:
    check = "launch-legal-truthfulness"
    path = _resolve_csv(LEGAL_ARTIFACT_REGISTER)
    if path is None:
        return
    rows = _read_csv(LEGAL_ARTIFACT_REGISTER)
    for row in rows:
        artifact_id = row.get("artifact_id", "")
        status = row.get("status", "").strip()
        review_date = row.get("last_review_date", "").strip()
        evidence_path = row.get("evidence_path", "").strip()
        jurisdictions = row.get("jurisdictions", "").strip()

        if review_date and not evidence_path:
            report.fail(check, f"{artifact_id}: last_review_date is set ('{review_date}') without an evidence_path to support it")

        if evidence_path:
            if not _is_safe_path(evidence_path):
                report.fail(check, f"{artifact_id}: unsafe evidence_path: {evidence_path}")
            elif not resolve_repo_path(evidence_path).is_file():
                report.fail(check, f"{artifact_id}: evidence_path does not exist: {evidence_path}")

        if status.lower() in {"reviewed", "approved"} and not evidence_path:
            report.fail(check, f"{artifact_id}: status '{status}' claims a completed review/approval without an evidence_path")

        if jurisdictions.lower() == "global":
            report.fail(check, f"{artifact_id}: jurisdictions claims unsupported blanket 'Global' coverage (use 'TBD' or a specific list)")

    if rows and not report.has_failures:
        report.ok(check, f"legal register contains no unsupported review/approval or jurisdiction claims across {len(rows)} artifact(s)")


# ---------------------------------------------------------------------------
# G. Support / rollback / launch-day runbook content
# ---------------------------------------------------------------------------


def _check_document_categories(report: Report, check: str, doc_path: str, categories: dict[str, list[str]]) -> None:
    text = _read_doc_text(doc_path)
    if text is None:
        report.fail(check, f"{doc_path} does not exist")
        return
    missing = [name for name, patterns in categories.items() if not any(re.search(p, text, re.IGNORECASE) for p in patterns)]
    if missing:
        report.fail(check, f"{doc_path} is missing required content categor{'y' if len(missing)==1 else 'ies'}: {missing}")
    else:
        report.ok(check, f"{doc_path} covers all {len(categories)} required content categories")


def check_support_plan_content(report: Report) -> None:
    _check_document_categories(report, "launch-support-plan-content", SUPPORT_OPERATIONS_PLAN, SUPPORT_PLAN_CATEGORIES)


def check_rollback_runbook_content(report: Report) -> None:
    _check_document_categories(report, "launch-rollback-runbook-content", RELEASE_ROLLBACK_RUNBOOK, ROLLBACK_RUNBOOK_CATEGORIES)


def check_launch_day_runbook_content(report: Report) -> None:
    _check_document_categories(report, "launch-day-runbook-content", LAUNCH_DAY_RUNBOOK, LAUNCH_DAY_RUNBOOK_CATEGORIES)


def run_all() -> Report:
    report = Report()
    rows = check_launch_item_schema(report)
    if rows:
        check_unique_launch_ids(report, rows)
        check_launch_item_id_format(report, rows)
        check_required_fields(report, rows)
        check_evidence_locations(report, rows)
        check_owner_volume_format(report, rows)
        check_supporting_volumes(report, rows)
        check_volume_numbers_in_range(report, rows)
        check_release_stage_and_gate(report, rows)
        check_severity_and_impact_values(report, rows)
        check_dependency_items(report, rows)
        check_launch_dependency_cycles(report, rows)
        check_evidence_required_values(report, rows)
        check_rollback_required(report, rows)
        check_legal_review_required(report, rows)
        check_gate_complete_evidence(report, rows)
        check_gate_progression(report, rows)
        check_commercial_release_dependencies(report, rows)
        check_live_trading_pilot_evidence(report, rows)
        check_required_transactional_emails(report)
        check_required_billing_scenarios(report)
        check_billing_historical_access_preserved(report)
        check_required_analytics_events(report)
        check_analytics_property_minimization(report)
        check_required_legal_artifacts(report)
        check_legal_register_truthfulness(report)
        check_support_plan_content(report)
        check_rollback_runbook_content(report)
        check_launch_day_runbook_content(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate launch readiness artifacts.")
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
