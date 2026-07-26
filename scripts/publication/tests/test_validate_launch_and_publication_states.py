"""Regression tests for launch readiness and publication state validators."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _repo  # noqa: E402
import validate_launch_readiness as vlr  # noqa: E402
import validate_publication_states as vps  # noqa: E402


def _make_genuine_docx(path: Path, text: str = "Test content") -> None:
    from docx import Document

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_paragraph(text)
    doc.save(str(path))


def _make_genuine_pdf(path: Path, text: str = "Test content") -> None:
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, text)
    c.save()


class RepoFixtureTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "docs" / "launch").mkdir(parents=True)
        (self.root / "docs" / "publication").mkdir(parents=True)
        self._patcher = mock.patch.object(_repo, "REPO_ROOT", self.root)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    def write_csv(self, rel_path: str, rows: list[dict]) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def write_file(self, rel_path: str, content: str) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    @staticmethod
    def fail_messages(report, check: str) -> list[str]:
        return [f.message for f in report.findings if f.check == check and f.severity == "FAIL"]

    def assertAnyFailContains(self, report, check: str, substring: str) -> None:
        messages = self.fail_messages(report, check)
        self.assertTrue(
            any(substring.lower() in m.lower() for m in messages),
            f"expected a FAIL on check '{check}' containing {substring!r}, got: {messages}",
        )


# ---------------------------------------------------------------------------
# Launch readiness validator fixtures
# ---------------------------------------------------------------------------


def _gate_row(item_id, name, owner, supporting, stage, gate, severity, status,
              evidence_location, approver, deps, customer_impact, security_impact):
    return {
        "launch_item_id": item_id,
        "name": name,
        "description": f"{name} description.",
        "category": "Launch Readiness",
        "owner_volume": owner,
        "supporting_volumes": supporting,
        "release_stage": stage,
        "applicable_gate": gate,
        "blocking_severity": severity,
        "implementation_status": status,
        "evidence_required": "Yes",
        "evidence_location": evidence_location,
        "verification_method": "Review",
        "approver_role": approver,
        "last_verified_date": "",
        "dependency_items": deps,
        "rollback_required": "Yes",
        "customer_impact": customer_impact,
        "security_impact": security_impact,
        "legal_review_required": "Yes",
        "notes": "fixture row.",
    }


def _base_gate_rows() -> list[dict]:
    return [
        _gate_row("LAUNCH-0001", "Founder Alpha Readiness", "DS-018", "DS-015",
                  "Stage 3 -- Founder Workstation Beta", "Founder Alpha Readiness", "Medium", "Planned",
                  "docs/launch/BETA_READINESS_CHECKLIST.md", "Founder Sponsor", "", "Founder-only", "High"),
        _gate_row("LAUNCH-0002", "Founder Beta Readiness", "DS-018", "DS-015",
                  "Stage 3 -- Founder Workstation Beta", "Founder Beta Readiness", "Medium", "Planned",
                  "docs/launch/BETA_READINESS_CHECKLIST.md", "Founder Sponsor", "LAUNCH-0001", "Founder-only", "High"),
        _gate_row("LAUNCH-0003", "Customer Beta Readiness", "DS-022", "DS-019",
                  "Stage 4 -- Customer Cloud Beta", "Customer Beta Readiness", "High", "Planned",
                  "docs/launch/BETA_READINESS_CHECKLIST.md", "Customer Beta Sponsor", "LAUNCH-0002", "Medium", "Medium"),
        _gate_row("LAUNCH-0004", "Billing and Subscription Readiness", "DS-019", "DS-023",
                  "Stage 5 -- Initial Commercial Release", "Commercial Release Readiness", "High", "Planned",
                  "docs/launch/BILLING_TEST_MATRIX.csv", "Billing Operations", "", "High", "High"),
        _gate_row("LAUNCH-0005", "Legal and Policy Readiness", "DS-021", "DS-019",
                  "Stage 5 -- Initial Commercial Release", "Commercial Release Readiness", "High", "Planned",
                  "docs/launch/LEGAL_AND_POLICY_ARTIFACT_REGISTER.csv", "Legal Counsel", "", "High", "High"),
        _gate_row("LAUNCH-0006", "Support Operations Readiness", "DS-023", "DS-022",
                  "Stage 5 -- Initial Commercial Release", "Commercial Release Readiness", "High", "Planned",
                  "docs/launch/SUPPORT_OPERATIONS_PLAN.md", "Operations Lead", "", "High", "High"),
        _gate_row("LAUNCH-0007", "Customer Communication Readiness", "DS-022", "DS-019",
                  "Stage 5 -- Initial Commercial Release", "Commercial Release Readiness", "High", "Planned",
                  "docs/launch/BETA_READINESS_CHECKLIST.md", "Launch Communications", "", "Medium", "Medium"),
        _gate_row("LAUNCH-0008", "Rollback and Recovery Readiness", "DS-023", "DS-019",
                  "Stage 5 -- Initial Commercial Release", "Commercial Release Readiness", "Critical", "Planned",
                  "docs/launch/RELEASE_ROLLBACK_RUNBOOK.md", "Operations Lead", "", "High", "High"),
        _gate_row("LAUNCH-0009", "Live-Trading Pilot Readiness", "DS-023", "DS-019",
                  "Stage 4 -- Customer Cloud Beta", "Live-Trading Pilot Readiness", "Critical", "Planned",
                  "docs/launch/COMMERCIAL_RELEASE_CHECKLIST.md", "Live Trading Review Board", "LAUNCH-0003", "High", "Very High"),
        _gate_row("LAUNCH-0010", "Commercial Release Readiness", "DS-019", "DS-023",
                  "Stage 5 -- Initial Commercial Release", "Commercial Release Readiness", "Critical", "Planned",
                  "docs/launch/COMMERCIAL_RELEASE_CHECKLIST.md", "Commercial Release Sponsor",
                  "LAUNCH-0003;LAUNCH-0004;LAUNCH-0005;LAUNCH-0006;LAUNCH-0007;LAUNCH-0008;LAUNCH-0009",
                  "High", "High"),
    ]


REQUIRED_EMAIL_PURPOSES = [
    "Email verification", "Password reset", "New-device login", "Security alert",
    "MFA recovery", "Subscription confirmation", "Payment receipt", "Failed payment",
    "Trial ending", "Grace period started", "Grace period ending",
    "Cancellation confirmation", "Support-case update", "Policy update notice",
    "Broker disconnected", "Data export ready", "Account deletion confirmation",
    "Automation halted", "Critical incident",
]


def _email_rows() -> list[dict]:
    rows = []
    for i, purpose in enumerate(REQUIRED_EMAIL_PURPOSES, start=1):
        rows.append({
            "template_id": f"EMAIL-{i:04d}", "purpose": purpose, "trigger": "trigger event",
            "required_fields": "field", "prohibited_sensitive_content": "Do not include secrets",
            "localization_readiness": "Planned", "delivery_tracking": "Yes",
            "retry_behavior": "Retry", "owning_service": "Service",
            "release_stage": "Stage 5 -- Initial Commercial Release", "notes": "fixture row.",
        })
    return rows


def _billing_rows() -> list[dict]:
    rows = []
    for i, event in enumerate(sorted(vlr.REQUIRED_BILLING_SCENARIO_EVENTS), start=1):
        if event in vlr.HISTORICAL_ACCESS_EVENTS:
            billing_state = "Suspended (active premium capabilities suspended; historical data retained read-only)"
            entitlement_state = "Suspended (read-only historical data and export retained)"
        else:
            billing_state = "Active"
            entitlement_state = "Retained"
        rows.append({
            "test_id": f"BILL-{i:04d}", "preconditions": "precondition", "event": event,
            "expected_billing_state": billing_state, "expected_entitlement_state": entitlement_state,
            "expected_customer_notification": "Notice sent", "audit_requirement": "Log event",
            "idempotency_expectation": "Idempotent", "rollback_recovery_behavior": "Recover safely",
            "release_gate": "Commercial Release Readiness", "notes": "fixture row.",
        })
    return rows


def _legal_rows() -> list[dict]:
    rows = []
    for i, name in enumerate(sorted(vlr.REQUIRED_LEGAL_ARTIFACTS), start=1):
        rows.append({
            "artifact_id": f"LEGAL-{i:04d}", "artifact_name": name, "owner": "DS-019",
            "reviewing_professional_role": "Legal Counsel",
            "required_stage": "Stage 5 -- Initial Commercial Release",
            "status": "Draft Not Reviewed", "last_review_date": "", "evidence_path": "",
            "jurisdictions": "TBD", "user_acceptance_required": "Yes",
            "change_notification_required": "Yes", "notes": "fixture row.",
        })
    return rows


def _analytics_rows() -> list[dict]:
    rows = []
    for name in sorted(vlr.REQUIRED_ANALYTICS_EVENTS):
        rows.append({
            "event_name": name, "purpose": "purpose", "trigger": "trigger",
            "properties": "user_id;context", "privacy_classification": "Pseudonymous",
            "consent_requirement": "None", "retention": "90 days",
            "owning_service": "Service", "owning_volume": "DS-022",
            "release_stage": "Stage 5 -- Initial Commercial Release", "notes": "fixture row.",
        })
    return rows


COMMERCIAL_CHECKLIST_TEXT = """# Commercial Release Checklist

## Live-Trading Pilot Evidence Requirements

Deterministic validation pipeline and broker state certification are documented.
Order idempotency, duplicate prevention, and reconciliation practices are defined.
Partial-fill handling, stale order handling, and unknown order state procedures are available.
Kill switches, exits-only mode, stop-loss/take-profit protections, and incident-response triggers are documented.
Continuous broker-state monitoring confirms connection health.
Independent security review of the live-trading path is completed.
Live unlock approval from the Live Trading Review Board is required.
Explicit customer consent to live-trading risk is captured before enrollment.
Full audit logging of every order is enabled.
Rollback readiness is confirmed before pilot entry.
"""

BETA_CHECKLIST_TEXT = "# Beta Readiness Checklist\n\nFounder and customer beta criteria.\n"

SUPPORT_PLAN_TEXT = """# Support Operations Plan

## Severity Levels and Response Targets

Severity levels define response targets for incident handling.

## Escalation and Decision Authority

Escalation paths define decision authority for approvals.

## Diagnostics

Diagnostic collection requires consent from the customer.

## Communication

Customer communication keeps customers informed.

## Evidence

Evidence capture and evidence location are recorded per incident.

## Closure

Closure criteria define when an incident is resolved.

## Post-Incident Review

A post-incident review is conducted after major incidents.
"""

ROLLBACK_RUNBOOK_TEXT = """# Release Rollback Runbook

## Rollback Triggers

Unknown or stale order state triggers a fail-closed rollback.

## Reconciliation

Broker reconciliation confirms order state after duplicate submissions are detected and prevented.

## Partial Fill

Validate partial fill handling for every order.

## Stale Acknowledgement

Stale orders with missing acknowledgement are escalated for manual review.

## Exits-Only Mode

Enable exits-only mode during automation halt.

## Kill Switch

Activate the kill switch immediately.

## Customer Communication

Notify affected customers about the rollback.

## Escalation

Escalate the incident to operations and security.

## Post-Rollback Validation

Confirm post-rollback validation before restoring service; the operations lead retains
ownership of the recovered state until sign-off.
"""

LAUNCH_DAY_RUNBOOK_TEXT = """# Launch Day Runbook

## Roles

1. Launch Director role approves go/no-go.
2. Operations Lead role monitors rollback triggers.

## Stop Conditions

Stop conditions pause the launch until resolved.

## Monitoring

Monitoring thresholds track incident escalation and evidence capture.

## Sign-off

The Launch Director signs off on the release.
"""


class TestLaunchReadinessValidator(RepoFixtureTestCase):
    def setUp(self):
        super().setUp()
        self.gate_rows = _base_gate_rows()
        self.email_rows = _email_rows()
        self.billing_rows = _billing_rows()
        self.legal_rows = _legal_rows()
        self.analytics_rows = _analytics_rows()
        self.write_file("docs/launch/BETA_READINESS_CHECKLIST.md", BETA_CHECKLIST_TEXT)
        self.write_file("docs/launch/SUPPORT_OPERATIONS_PLAN.md", SUPPORT_PLAN_TEXT)
        self.write_file("docs/launch/RELEASE_ROLLBACK_RUNBOOK.md", ROLLBACK_RUNBOOK_TEXT)
        self.write_file("docs/launch/LAUNCH_DAY_RUNBOOK.md", LAUNCH_DAY_RUNBOOK_TEXT)
        self.write_file("docs/launch/COMMERCIAL_RELEASE_CHECKLIST.md", COMMERCIAL_CHECKLIST_TEXT)

    def write_all(self, gate_rows=None, email_rows=None, billing_rows=None, legal_rows=None, analytics_rows=None):
        self.write_csv(vlr.LAUNCH_MATRIX, gate_rows if gate_rows is not None else self.gate_rows)
        self.write_csv(vlr.TRANSACTIONAL_EMAIL_REGISTER, email_rows if email_rows is not None else self.email_rows)
        self.write_csv(vlr.BILLING_TEST_MATRIX, billing_rows if billing_rows is not None else self.billing_rows)
        self.write_csv(vlr.LEGAL_ARTIFACT_REGISTER, legal_rows if legal_rows is not None else self.legal_rows)
        self.write_csv(vlr.PRODUCT_ANALYTICS_EVENT_REGISTER, analytics_rows if analytics_rows is not None else self.analytics_rows)

    def _row(self, rows, item_id):
        return next(r for r in rows if r["launch_item_id"] == item_id)

    # 27. valid fixture passes
    def test_valid_launch_fixture_passes(self):
        self.write_all()
        report = vlr.run_all()
        self.assertFalse(report.has_failures, report.findings)

    # 2. missing Founder Beta gate
    def test_missing_founder_beta_gate_fails(self):
        rows = [r for r in self.gate_rows if r["launch_item_id"] != "LAUNCH-0002"]
        self.write_all(gate_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-gate-progression", "Founder Beta Readiness")

    # 3. broken Alpha -> Beta dependency
    def test_broken_alpha_to_beta_dependency_fails(self):
        rows = [dict(r) for r in self.gate_rows]
        self._row(rows, "LAUNCH-0002")["dependency_items"] = ""
        self.write_all(gate_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-gate-progression", "Alpha -> Beta")

    # 4. broken Beta -> Customer Beta dependency
    def test_broken_beta_to_customer_beta_dependency_fails(self):
        rows = [dict(r) for r in self.gate_rows]
        self._row(rows, "LAUNCH-0003")["dependency_items"] = ""
        self.write_all(gate_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-gate-progression", "Beta -> Customer Beta")

    # 5. Commercial Release missing billing readiness
    def test_commercial_release_missing_billing_fails(self):
        rows = [dict(r) for r in self.gate_rows]
        commercial = self._row(rows, "LAUNCH-0010")
        commercial["dependency_items"] = commercial["dependency_items"].replace("LAUNCH-0004;", "")
        self.write_all(gate_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-commercial-release-dependencies", "billing readiness")

    # 6. Commercial Release missing rollback readiness
    def test_commercial_release_missing_rollback_fails(self):
        rows = [dict(r) for r in self.gate_rows]
        commercial = self._row(rows, "LAUNCH-0010")
        commercial["dependency_items"] = commercial["dependency_items"].replace("LAUNCH-0008;", "").replace(";LAUNCH-0008", "")
        self.write_all(gate_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-commercial-release-dependencies", "rollback readiness")

    # 7. Commercial Release missing legal readiness
    def test_commercial_release_missing_legal_fails(self):
        rows = [dict(r) for r in self.gate_rows]
        commercial = self._row(rows, "LAUNCH-0010")
        commercial["dependency_items"] = commercial["dependency_items"].replace("LAUNCH-0005;", "")
        self.write_all(gate_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-commercial-release-dependencies", "legal/policy readiness")

    # 8. Live pilot missing deterministic pipeline evidence
    def test_live_pilot_missing_deterministic_pipeline_evidence_fails(self):
        text = COMMERCIAL_CHECKLIST_TEXT.replace("Deterministic validation pipeline and broker state certification are documented.\n", "")
        self.write_file("docs/launch/COMMERCIAL_RELEASE_CHECKLIST.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-live-trading-pilot-evidence", "deterministic validation pipeline")

    # 9. Live pilot missing reconciliation evidence
    def test_live_pilot_missing_reconciliation_evidence_fails(self):
        text = COMMERCIAL_CHECKLIST_TEXT.replace(", and reconciliation practices are defined", " practices are defined")
        self.write_file("docs/launch/COMMERCIAL_RELEASE_CHECKLIST.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-live-trading-pilot-evidence", "reconciliation")

    # 10. Live pilot missing duplicate-prevention evidence
    def test_live_pilot_missing_duplicate_prevention_evidence_fails(self):
        text = COMMERCIAL_CHECKLIST_TEXT.replace("duplicate prevention, and reconciliation", "reconciliation")
        self.write_file("docs/launch/COMMERCIAL_RELEASE_CHECKLIST.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-live-trading-pilot-evidence", "duplicate prevention")

    # 11. Missing Automation Halted email
    def test_missing_automation_halted_email_fails(self):
        rows = [r for r in self.email_rows if r["purpose"] != "Automation halted"]
        self.write_all(email_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-transactional-emails", "automation halted")

    # 12. Missing Critical Incident email
    def test_missing_critical_incident_email_fails(self):
        rows = [r for r in self.email_rows if r["purpose"] != "Critical incident"]
        self.write_all(email_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-transactional-emails", "critical incident")

    # 13. Cancellation removes historical access
    def test_cancellation_removes_historical_access_fails(self):
        rows = [dict(r) for r in self.billing_rows]
        for r in rows:
            if r["event"] == "Subscription cancelled":
                r["expected_billing_state"] = "Cancelled"
                r["expected_entitlement_state"] = "Removed"
        self.write_all(billing_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-billing-historical-access", "Subscription cancelled")

    # 14. Grace expiration removes historical access
    def test_grace_expiration_removes_historical_access_fails(self):
        rows = [dict(r) for r in self.billing_rows]
        for r in rows:
            if r["event"] == "Grace-period expiration":
                r["expected_billing_state"] = "Past due"
                r["expected_entitlement_state"] = "Suspended"
        self.write_all(billing_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-billing-historical-access", "Grace-period expiration")

    # 15. Suspension removes historical access
    def test_suspension_removes_historical_access_fails(self):
        rows = [dict(r) for r in self.billing_rows]
        for r in rows:
            if r["event"] == "Account suspension":
                r["expected_billing_state"] = "Suspended"
                r["expected_entitlement_state"] = "Removed"
        self.write_all(billing_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-billing-historical-access", "Account suspension")

    # 16. profile_summary analytics property rejected
    def test_profile_summary_analytics_property_rejected(self):
        rows = [dict(r) for r in self.analytics_rows]
        rows[0]["properties"] = "user_id;profile_summary"
        self.write_all(analytics_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-analytics-minimization", "profile_summary")

    # 17. broker_credentials analytics property rejected
    def test_broker_credentials_analytics_property_rejected(self):
        rows = [dict(r) for r in self.analytics_rows]
        rows[0]["properties"] = "user_id;broker_credentials"
        self.write_all(analytics_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-analytics-minimization", "broker_credentials")

    # 18. fabricated legal review date rejected
    def test_fabricated_legal_review_date_rejected(self):
        rows = [dict(r) for r in self.legal_rows]
        rows[0]["last_review_date"] = "2026-01-01"
        rows[0]["evidence_path"] = ""
        self.write_all(legal_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-legal-truthfulness", "without an evidence_path")

    # 19. nonexistent legal evidence path rejected
    def test_nonexistent_legal_evidence_path_rejected(self):
        rows = [dict(r) for r in self.legal_rows]
        rows[0]["evidence_path"] = "docs/legal/does-not-exist.md"
        self.write_all(legal_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-legal-truthfulness", "does not exist")

    # 20. unsupported Global jurisdiction rejected
    def test_unsupported_global_jurisdiction_rejected(self):
        rows = [dict(r) for r in self.legal_rows]
        rows[0]["jurisdictions"] = "Global"
        self.write_all(legal_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-legal-truthfulness", "Global")

    # 21. reviewed/approved status without evidence rejected
    def test_reviewed_status_without_evidence_rejected(self):
        rows = [dict(r) for r in self.legal_rows]
        rows[0]["status"] = "Approved"
        rows[0]["evidence_path"] = ""
        self.write_all(legal_rows=rows)
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-legal-truthfulness", "review/approval")

    # 22. support plan missing severity levels
    def test_support_plan_missing_severity_levels_fails(self):
        text = SUPPORT_PLAN_TEXT.replace("## Severity Levels and Response Targets\n\nSeverity levels define response targets for incident handling.\n\n", "")
        self.write_file("docs/launch/SUPPORT_OPERATIONS_PLAN.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-support-plan-content", "severity levels")

    # 23. support plan missing escalation
    def test_support_plan_missing_escalation_fails(self):
        text = SUPPORT_PLAN_TEXT.replace("## Escalation and Decision Authority\n\nEscalation paths define decision authority for approvals.\n\n", "")
        self.write_file("docs/launch/SUPPORT_OPERATIONS_PLAN.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-support-plan-content", "escalation")

    # 24. rollback runbook missing fail-closed unknown-order handling
    def test_rollback_runbook_missing_unknown_order_failclosed_fails(self):
        text = ROLLBACK_RUNBOOK_TEXT.replace("Unknown or stale order state triggers a fail-closed rollback.", "Unknown or stale order state triggers a rollback.")
        self.write_file("docs/launch/RELEASE_ROLLBACK_RUNBOOK.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-rollback-runbook-content", "fail-closed")

    # 25. rollback runbook missing reconciliation
    def test_rollback_runbook_missing_reconciliation_fails(self):
        text = ROLLBACK_RUNBOOK_TEXT.replace(
            "## Reconciliation\n\nBroker reconciliation confirms order state after duplicate submissions are detected and prevented.\n\n",
            "",
        )
        self.write_file("docs/launch/RELEASE_ROLLBACK_RUNBOOK.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-rollback-runbook-content", "reconciliation")

    # 26. rollback runbook missing duplicate prevention
    def test_rollback_runbook_missing_duplicate_prevention_fails(self):
        text = ROLLBACK_RUNBOOK_TEXT.replace("after duplicate submissions are detected and prevented", "after submissions are detected")
        self.write_file("docs/launch/RELEASE_ROLLBACK_RUNBOOK.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-rollback-runbook-content", "duplicate prevention")

    # 1. launch-day runbook missing go/no-go criteria
    def test_launchday_runbook_missing_gonogo_fails(self):
        text = LAUNCH_DAY_RUNBOOK_TEXT.replace("Launch Director role approves go/no-go.", "Launch Director role approves the launch.")
        self.write_file("docs/launch/LAUNCH_DAY_RUNBOOK.md", text)
        self.write_all()
        report = vlr.run_all()
        self.assertAnyFailContains(report, "launch-day-runbook-content", "go/no-go criteria")


# ---------------------------------------------------------------------------
# Publication state validator fixtures
# ---------------------------------------------------------------------------


class TestPublicationStateValidator(RepoFixtureTestCase):
    def _write_markdown(self, volume_id: str) -> str:
        rel = f"docs/codex/{volume_id}.md"
        self.write_file(rel, f"# {volume_id} placeholder\n")
        return rel

    def _write_evidence(self, volume_id: str) -> str:
        rel = f"docs/publication/evidence/{volume_id}-review.md"
        self.write_file(rel, f"# {volume_id} independent review evidence\n")
        return rel

    def build_released_row(self, volume_id: str, legacy: bool) -> dict:
        md = self._write_markdown(volume_id)
        docx_rel = f"docs/publication/releases/{volume_id}.docx"
        pdf_rel = f"docs/publication/releases/{volume_id}.pdf"
        _make_genuine_docx(self.root / docx_rel, f"{volume_id} content")
        _make_genuine_pdf(self.root / pdf_rel, f"{volume_id} content")
        evidence = self._write_evidence(volume_id)
        return {
            "volume_id": volume_id, "title": f"{volume_id} Title", "publication_state": "Released",
            "markdown_path": md, "docx_path": docx_rel, "pdf_path": pdf_rel,
            "metadata_verified": "Yes", "traceability_complete": "Yes",
            "controlled_ids_valid": "Yes", "acceptance_criteria_complete": "Yes",
            "independent_review_complete": "Yes", "independent_review_evidence": evidence,
            "checksum_verified": "Yes",
            "release_manifest_entry": "docs/publication/PUBLICATION_MANIFEST.json",
            "approved_by": "" if legacy else "Governance Board",
            "approved_date": "" if legacy else "2025-12-01",
            "blocker": "", "notes": "Released Core volume." if legacy else "note",
        }

    def build_skeleton_row(self, volume_id: str) -> dict:
        md = self._write_markdown(volume_id)
        return {
            "volume_id": volume_id, "title": f"{volume_id} Title", "publication_state": "Skeleton",
            "markdown_path": md, "docx_path": "", "pdf_path": "",
            "metadata_verified": "No", "traceability_complete": "No",
            "controlled_ids_valid": "No", "acceptance_criteria_complete": "No",
            "independent_review_complete": "No", "independent_review_evidence": "",
            "checksum_verified": "No", "release_manifest_entry": "",
            "approved_by": "", "approved_date": "", "blocker": "", "notes": "Not Released",
        }

    def manifest_entries_for(self, rows: list[dict]) -> list[dict]:
        entries = []
        for row in rows:
            if row["publication_state"] != "Released":
                continue
            for field_name, artifact_type in (("markdown_path", "markdown"), ("docx_path", "docx"), ("pdf_path", "pdf")):
                rel = row[field_name]
                abs_path = self.root / rel
                entries.append({
                    "document_id": row["volume_id"],
                    "artifact_type": artifact_type,
                    "planned_artifact_path": rel,
                    "generated": True,
                    "checksum": _repo.sha256_of_file(abs_path),
                    "byte_count": abs_path.stat().st_size,
                })
        return entries

    def write_manifest(self, entries: list[dict]) -> None:
        path = self.root / vps.MANIFEST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"baseline_commit": "test", "entries": entries}), encoding="utf-8")

    def full_valid_rows(self) -> list[dict]:
        rows = [self.build_released_row(f"DS-{i:03d}", legacy=True) for i in range(1, 15)]
        rows += [self.build_skeleton_row(f"DS-{i:03d}") for i in range(15, 24)]
        return rows

    def write_full_valid_fixture(self) -> list[dict]:
        rows = self.full_valid_rows()
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(self.manifest_entries_for(rows))
        return rows

    # 46. Honest legacy Core Released fixture with genuine DOCX/PDF and matching manifest passes
    def test_valid_publication_state_fixture_passes(self):
        self.write_full_valid_fixture()
        report = vps.run_all()
        self.assertFalse(report.has_failures, report.findings)

    # 28. Duplicate volume rejected
    def test_duplicate_publication_volume_fails(self):
        rows = self.full_valid_rows()
        rows.append(dict(rows[0]))
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(self.manifest_entries_for(rows))
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-duplicate-volume", "DS-001")

    # 29. Missing required volume rejected
    def test_missing_publication_volume_fails(self):
        rows = self.full_valid_rows()[:-1]
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(self.manifest_entries_for(rows))
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-required-states", "missing expected publication volume rows")

    # 30. DS-024 rejected
    def test_ds024_rejected(self):
        rows = self.full_valid_rows()
        extra = self.build_skeleton_row("DS-024")
        rows.append(extra)
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(self.manifest_entries_for(rows))
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-volume-range", "DS-024")

    # 31. Path traversal rejected
    def test_path_traversal_rejected(self):
        rows = self.full_valid_rows()
        rows[0] = dict(rows[0])
        rows[0]["docx_path"] = "../outside.docx"
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(self.manifest_entries_for(self.full_valid_rows()))
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-path-safety", "unsafe")

    # 32. Released missing DOCX rejected
    def test_released_missing_docx_rejected(self):
        rows = self.full_valid_rows()
        entries = self.manifest_entries_for(rows)
        rows[0] = dict(rows[0])
        rows[0]["docx_path"] = ""
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "missing docx_path")

    # 33. Released missing PDF rejected
    def test_released_missing_pdf_rejected(self):
        rows = self.full_valid_rows()
        entries = self.manifest_entries_for(rows)
        rows[0] = dict(rows[0])
        rows[0]["pdf_path"] = ""
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "missing pdf_path")

    # 34. Fake text DOCX rejected
    def test_fake_text_docx_rejected(self):
        rows = self.write_full_valid_fixture()
        docx_path = self.root / rows[0]["docx_path"]
        docx_path.write_text("not a real docx", encoding="utf-8")
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "not a genuine DOCX")

    # 35. Fake text PDF rejected
    def test_fake_text_pdf_rejected(self):
        rows = self.write_full_valid_fixture()
        pdf_path = self.root / rows[0]["pdf_path"]
        pdf_path.write_text("not a real pdf", encoding="utf-8")
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "not a genuine PDF")

    # 36. Manifest missing markdown entry rejected
    def test_manifest_missing_markdown_entry_rejected(self):
        rows = self.full_valid_rows()
        entries = [e for e in self.manifest_entries_for(rows) if not (e["document_id"] == "DS-001" and e["artifact_type"] == "markdown")]
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "no markdown entry")

    # 37. Manifest missing DOCX entry rejected
    def test_manifest_missing_docx_entry_rejected(self):
        rows = self.full_valid_rows()
        entries = [e for e in self.manifest_entries_for(rows) if not (e["document_id"] == "DS-001" and e["artifact_type"] == "docx")]
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "no docx entry")

    # 38. Manifest missing PDF entry rejected
    def test_manifest_missing_pdf_entry_rejected(self):
        rows = self.full_valid_rows()
        entries = [e for e in self.manifest_entries_for(rows) if not (e["document_id"] == "DS-001" and e["artifact_type"] == "pdf")]
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "no pdf entry")

    # 39. Byte-count mismatch rejected
    def test_byte_count_mismatch_rejected(self):
        rows = self.full_valid_rows()
        entries = self.manifest_entries_for(rows)
        for e in entries:
            if e["document_id"] == "DS-001" and e["artifact_type"] == "docx":
                e["byte_count"] = e["byte_count"] + 12345
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "byte_count mismatch")

    # 40. SHA-256 mismatch rejected
    def test_sha256_mismatch_rejected(self):
        rows = self.full_valid_rows()
        entries = self.manifest_entries_for(rows)
        for e in entries:
            if e["document_id"] == "DS-001" and e["artifact_type"] == "docx":
                e["checksum"] = "0" * 64
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "checksum mismatch")

    # 41. Released missing independent review evidence rejected (legacy exception does not cover it)
    def test_released_missing_independent_review_evidence_rejected(self):
        rows = self.full_valid_rows()
        entries = self.manifest_entries_for(rows)
        rows[4] = dict(rows[4])  # DS-005, a legacy Core volume
        rows[4]["independent_review_evidence"] = ""
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "missing independent_review_evidence")

    # 42. Fabricated approver rejected (missing approved_by outside the legacy exception)
    def test_fabricated_approver_rejected(self):
        rows = self.full_valid_rows()
        released_16 = self.build_released_row("DS-016", legacy=False)
        released_16["approved_by"] = ""
        rows = [r for r in rows if r["volume_id"] != "DS-016"] + [released_16]
        entries = self.manifest_entries_for(rows)
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "missing approved_by")

    # 43. Fabricated approval date rejected (missing approved_date outside the legacy exception)
    def test_fabricated_approval_date_rejected(self):
        rows = self.full_valid_rows()
        released_16 = self.build_released_row("DS-016", legacy=False)
        released_16["approved_date"] = ""
        rows = [r for r in rows if r["volume_id"] != "DS-016"] + [released_16]
        entries = self.manifest_entries_for(rows)
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "missing approved_date")

    # 44. Expansion volume marked Released rejected
    def test_expansion_volume_released_rejected(self):
        rows = self.full_valid_rows()
        released_16 = self.build_released_row("DS-016", legacy=False)
        rows = [r for r in rows if r["volume_id"] != "DS-016"] + [released_16]
        entries = self.manifest_entries_for(rows)
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(entries)
        report = vps.run_all()
        self.assertAnyFailContains(report, "publication-release-artifacts", "must not be released")

    # 45. True Draft without binaries passes
    def test_draft_without_binaries_passes(self):
        rows = self.full_valid_rows()
        for row in rows:
            if row["volume_id"] == "DS-015":
                row["publication_state"] = "Draft"
        self.write_csv(vps.STATE_REGISTER, rows)
        self.write_manifest(self.manifest_entries_for(rows))
        report = vps.run_all()
        self.assertFalse(report.has_failures, report.findings)


if __name__ == "__main__":
    unittest.main()
