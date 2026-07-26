"""Regression tests for scripts/publication/validate_feature_registry.py.

Every filesystem-dependent test operates inside a throwaway tempfile.
TemporaryDirectory tree with _repo.REPO_ROOT monkeypatched to point at it,
mirroring test_publication_tools.py's RepoFixtureTestCase pattern -- nothing
here reads or writes the actual repository tree.

Each test builds a minimal, otherwise-valid fixture registry (and companion
files where relevant), mutates exactly one thing, and asserts the expected
check fails (or, for the baseline case, that nothing fails).
"""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _repo  # noqa: E402
import validate_feature_registry as vfr  # noqa: E402


REGISTRY_HEADER = vfr.REQUIRED_COLUMNS


def _base_row(**overrides) -> dict:
    row = {c: "" for c in REGISTRY_HEADER}
    row.update({
        "feature_id": "FEAT-9001",
        "feature_name": "Fixture feature",
        "category": "99 Fixture",
        "summary": "A fixture feature for validator regression tests.",
        "purpose": "Exercise the validator.",
        "owner_volume": "DS-002",
        "supporting_volumes": "",
        "implementation_status": "Idea",
        "release_stage": "Stage 6 -- Advanced Trading Expansion",
        "priority": "Low",
        "initial_release_required": "No",
        "groundwork_required_now": "Can Be Added Later Without Current Architectural Work",
        "platform_availability": "Windows;Web;iOS;Android",
        "edition_availability": "Founder;Customer",
        "dependencies": "",
        "risk_level": "Low",
        "safety_classification": "N/A",
        "UX_location": "N/A",
        "API_or_service_owner": "N/A",
        "acceptance_summary": "TBD -- requirement not yet fully drafted",
        "design_evidence": "Not Yet Designed",
        "implementation_evidence": "None",
        "test_evidence": "None",
        "release_evidence": "None -- not released",
        "blocker": "None",
        "tentative_start_window": "TBD",
        "tentative_completion_window": "TBD",
        "timeline_confidence": "Low",
        "release_history": "Created for validator regression test.",
        "replacement_feature": "",
        "deprecation_notes": "",
    })
    row.update(overrides)
    return row


class RegistryFixtureTestCase(unittest.TestCase):
    """Builds a fake repo tree containing a minimal, valid feature registry
    (+ companion files) and points _repo.REPO_ROOT at it for each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "docs" / "features").mkdir(parents=True)
        (self.root / "scripts" / "publication").mkdir(parents=True)
        self._patcher = mock.patch.object(_repo, "REPO_ROOT", self.root)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    def write_registry(self, rows) -> None:
        path = self.root / vfr.REGISTRY_PATH
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=REGISTRY_HEADER)
            w.writeheader()
            w.writerows(rows)

    def write_dependencies(self, edges) -> None:
        path = self.root / vfr.DEPENDENCIES_PATH
        header = ["feature_id", "feature_name", "depends_on_feature_id", "depends_on_feature_name", "dependency_type", "notes"]
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(edges)

    def write_matrix(self, path_attr, rows, columns) -> None:
        path = self.root / getattr(vfr, path_attr)
        header = ["feature_id", "feature_name"] + list(columns) + ["notes"]
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(rows)

    def write_tradingview(self, text: str) -> None:
        path = self.root / vfr.TRADINGVIEW_PATH
        path.write_text(text, encoding="utf-8")

    def setup_valid_fixture(self, rows=None):
        rows = rows if rows is not None else [_base_row()]
        self.write_registry(rows)
        self.write_dependencies([])
        self.write_matrix(
            "PLATFORM_MATRIX_PATH",
            [self._platform_row(r) for r in rows],
            vfr.CLIENT_PLATFORMS,
        )
        self.write_matrix(
            "EDITION_MATRIX_PATH",
            [self._edition_row(r) for r in rows],
            ("Founder", "Customer"),
        )
        self.write_tradingview("# Fixture\n\n| Cap | Class | feature_id | Notes |\n|---|---|---|---|\n")
        return rows

    @staticmethod
    def _platform_row(r):
        vals = {v.strip() for v in r["platform_availability"].split(";") if v.strip()}
        out = {"feature_id": r["feature_id"], "feature_name": r["feature_name"], "notes": ""}
        for col in vfr.CLIENT_PLATFORMS:
            out[col] = "N/A" if vals == {"N/A"} or not vals else ("Yes" if col in vals else "No")
        return out

    @staticmethod
    def _edition_row(r):
        vals = {v.strip() for v in r["edition_availability"].split(";") if v.strip()}
        out = {"feature_id": r["feature_id"], "feature_name": r["feature_name"], "notes": ""}
        for col in ("Founder", "Customer"):
            out[col] = "N/A" if vals == {"N/A"} or not vals else ("Yes" if col in vals else "No")
        return out

    def failing_checks(self):
        report = vfr.run_all()
        return {f.check for f in report.findings if f.severity == "FAIL"}


class TestValidFixturePasses(RegistryFixtureTestCase):
    def test_minimal_valid_fixture_has_no_failures(self):
        self.setup_valid_fixture()
        self.assertEqual(self.failing_checks(), set())

    def test_two_valid_features_with_dependency_edge_pass(self):
        rows = [
            _base_row(feature_id="FEAT-9001", dependencies="FEAT-9002"),
            _base_row(feature_id="FEAT-9002", feature_name="Fixture dependency"),
        ]
        self.write_registry(rows)
        self.write_dependencies([{
            "feature_id": "FEAT-9001", "feature_name": "Fixture feature",
            "depends_on_feature_id": "FEAT-9002", "depends_on_feature_name": "Fixture dependency",
            "dependency_type": "requires", "notes": "",
        }])
        self.write_matrix("PLATFORM_MATRIX_PATH", [self._platform_row(r) for r in rows], vfr.CLIENT_PLATFORMS)
        self.write_matrix("EDITION_MATRIX_PATH", [self._edition_row(r) for r in rows], ("Founder", "Customer"))
        self.write_tradingview("# Fixture\n")
        self.assertEqual(self.failing_checks(), set())


class TestDependencyCycleChecks(RegistryFixtureTestCase):
    def test_direct_self_dependency_fails(self):
        rows = [_base_row(feature_id="FEAT-9001", dependencies="FEAT-9001")]
        self.write_registry(rows)
        self.write_dependencies([{
            "feature_id": "FEAT-9001", "feature_name": "Fixture feature",
            "depends_on_feature_id": "FEAT-9001", "depends_on_feature_name": "Fixture feature",
            "dependency_type": "requires", "notes": "Self-dependency test",
        }])
        self.write_matrix("PLATFORM_MATRIX_PATH", [self._platform_row(r) for r in rows], vfr.CLIENT_PLATFORMS)
        self.write_matrix("EDITION_MATRIX_PATH", [self._edition_row(r) for r in rows], ("Founder", "Customer"))
        self.write_tradingview("# Fixture\n")
        self.assertIn("dependency-graph-acyclic", self.failing_checks())

    def test_two_node_cycle_fails(self):
        rows = [
            _base_row(feature_id="FEAT-9001", dependencies="FEAT-9002"),
            _base_row(feature_id="FEAT-9002", feature_name="Fixture dependency", dependencies="FEAT-9001"),
        ]
        self.write_registry(rows)
        self.write_dependencies([
            {
                "feature_id": "FEAT-9001", "feature_name": "Fixture feature",
                "depends_on_feature_id": "FEAT-9002", "depends_on_feature_name": "Fixture dependency",
                "dependency_type": "requires", "notes": "Cycle edge",
            },
            {
                "feature_id": "FEAT-9002", "feature_name": "Fixture dependency",
                "depends_on_feature_id": "FEAT-9001", "depends_on_feature_name": "Fixture feature",
                "dependency_type": "requires", "notes": "Cycle edge",
            },
        ])
        self.write_matrix("PLATFORM_MATRIX_PATH", [self._platform_row(r) for r in rows], vfr.CLIENT_PLATFORMS)
        self.write_matrix("EDITION_MATRIX_PATH", [self._edition_row(r) for r in rows], ("Founder", "Customer"))
        self.write_tradingview("# Fixture\n")
        self.assertIn("dependency-graph-acyclic", self.failing_checks())

    def test_longer_cycle_fails(self):
        rows = [
            _base_row(feature_id="FEAT-9001", dependencies="FEAT-9002"),
            _base_row(feature_id="FEAT-9002", feature_name="Fixture dependency", dependencies="FEAT-9003"),
            _base_row(feature_id="FEAT-9003", feature_name="Fixture dependency 2", dependencies="FEAT-9001"),
        ]
        self.write_registry(rows)
        self.write_dependencies([
            {
                "feature_id": "FEAT-9001", "feature_name": "Fixture feature",
                "depends_on_feature_id": "FEAT-9002", "depends_on_feature_name": "Fixture dependency",
                "dependency_type": "requires", "notes": "Cycle edge",
            },
            {
                "feature_id": "FEAT-9002", "feature_name": "Fixture dependency",
                "depends_on_feature_id": "FEAT-9003", "depends_on_feature_name": "Fixture dependency 2",
                "dependency_type": "requires", "notes": "Cycle edge",
            },
            {
                "feature_id": "FEAT-9003", "feature_name": "Fixture dependency 2",
                "depends_on_feature_id": "FEAT-9001", "depends_on_feature_name": "Fixture feature",
                "dependency_type": "requires", "notes": "Cycle edge",
            },
        ])
        self.write_matrix("PLATFORM_MATRIX_PATH", [self._platform_row(r) for r in rows], vfr.CLIENT_PLATFORMS)
        self.write_matrix("EDITION_MATRIX_PATH", [self._edition_row(r) for r in rows], ("Founder", "Customer"))
        self.write_tradingview("# Fixture\n")
        self.assertIn("dependency-graph-acyclic", self.failing_checks())

    def test_dependency_graph_includes_target_only_nodes(self):
        rows = [
            _base_row(feature_id="FEAT-9001", dependencies="FEAT-9002"),
            _base_row(feature_id="FEAT-9002", feature_name="Fixture dependency"),
        ]
        self.write_registry(rows)
        self.write_dependencies([{
            "feature_id": "FEAT-9001", "feature_name": "Fixture feature",
            "depends_on_feature_id": "FEAT-9002", "depends_on_feature_name": "Fixture dependency",
            "dependency_type": "requires", "notes": "Target-only node",
        }])
        self.write_matrix("PLATFORM_MATRIX_PATH", [self._platform_row(r) for r in rows], vfr.CLIENT_PLATFORMS)
        self.write_matrix("EDITION_MATRIX_PATH", [self._edition_row(r) for r in rows], ("Founder", "Customer"))
        self.write_tradingview("# Fixture\n")
        self.assertEqual(self.failing_checks(), set())


class TestEvidenceRules(RegistryFixtureTestCase):
    def test_designed_with_empty_evidence_fails(self):
        self.setup_valid_fixture([_base_row(
            implementation_status="Designed",
            design_evidence="",
            acceptance_summary="Design documented in DS-015 §7.",
        )])
        self.assertIn("designed-status-requires-real-design-evidence", self.failing_checks())

    def test_designed_with_not_yet_designed_evidence_fails(self):
        self.setup_valid_fixture([_base_row(
            implementation_status="Designed",
            design_evidence="Not Yet Designed",
            acceptance_summary="Design documented in DS-015 §7.",
        )])
        self.assertIn("designed-status-requires-real-design-evidence", self.failing_checks())

    def test_designed_with_valid_evidence_passes(self):
        self.setup_valid_fixture([_base_row(
            implementation_status="Designed",
            design_evidence="DS-015 §7",
            acceptance_summary="Design documented in DS-015 §7.",
        )])
        self.assertEqual(self.failing_checks(), set())

    def test_removed_without_removal_evidence_fails(self):
        self.setup_valid_fixture([_base_row(
            implementation_status="Removed",
            release_evidence="",
            deprecation_notes="Removed per product registry and replaced by FEAT-9999.",
            acceptance_summary="This feature was removed and replaced by FEAT-9999.",
        )])
        self.assertIn("status-evidence-discipline", self.failing_checks())

    def test_removed_without_migration_disposition_evidence_fails(self):
        self.setup_valid_fixture([_base_row(
            implementation_status="Removed",
            release_evidence="Removed in 2026-07",
            deprecation_notes="Deprecated due to duplicate feature.",
            acceptance_summary="This feature was removed; see release notes.",
        )])
        self.assertIn("status-evidence-discipline", self.failing_checks())


class TestFeat0268Representation(unittest.TestCase):
    REPO_ROOT = Path(__file__).resolve().parents[3]

    def _doc_text(self, rel_path: str) -> str:
        path = self.REPO_ROOT / rel_path
        self.assertTrue(path.is_file(), f"Missing expected doc file: {rel_path}")
        return path.read_text(encoding="utf-8")

    def _registry_rows(self):
        path = self.REPO_ROOT / "docs/features/FEATURE_REGISTRY.csv"
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _registry_row(self, feature_id: str):
        rows = self._registry_rows()
        for row in rows:
            if row["feature_id"] == feature_id:
                return row
        self.fail(f"Feature {feature_id} not found in registry")

    def _assert_doc_mentions(self, rel_path: str, phrase: str):
        self.assertIn(phrase, self._doc_text(rel_path), f"{rel_path} missing required phrase: {phrase!r}")

    def test_ds015_mentions_feat_0268(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-15-Editions/DS-015-Product-Editions-and-Repository-Architecture.md",
            "FEAT-0268",
        )

    def test_ds018_mentions_feat_0268(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-18-SageDeployment/DS-018-Sage-Deployment-and-Intelligence-Architecture.md",
            "FEAT-0268",
        )

    def test_ds021_mentions_feat_0268(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-21-SecurityDeviceTrust/DS-021-Security-Device-Trust-Privacy-and-IP-Protection.md",
            "FEAT-0268",
        )

    def test_ds023_mentions_feat_0268(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-23-Reliability/DS-023-Reliability-Operations-Data-Governance-and-Recovery.md",
            "FEAT-0268",
        )

    def test_feature_timeline_mentions_founder_sage_developer_mode(self):
        self._assert_doc_mentions(
            "docs/features/FEATURE_TIMELINE.md",
            "Founder Sage Developer Mode",
        )

    def test_feature_dependencies_includes_feat_0268(self):
        text = self._doc_text("docs/features/FEATURE_DEPENDENCIES.csv")
        self.assertIn("FEAT-0268,Founder Sage Developer Mode", text)

    def test_registry_dependency_summary_for_feat_0268(self):
        row = self._registry_row("FEAT-0268")
        self.assertEqual(
            row["dependencies"],
            "FEAT-0001;FEAT-0002;FEAT-0122;FEAT-0008;FEAT-0249;FEAT-0247;FEAT-0251",
        )

    def test_complete_features_mentions_feat_0268(self):
        self._assert_doc_mentions("docs/features/DARKSAGE_COMPLETE_FEATURES.md", "Founder Sage Developer Mode")

    def test_feature_governance_mentions_feat_0268(self):
        self._assert_doc_mentions("docs/features/FEATURE_GOVERNANCE.md", "Founder Sage Developer Mode")

    def test_feature_changelog_mentions_feat_0268(self):
        self._assert_doc_mentions("docs/features/FEATURE_CHANGELOG.md", "Founder Sage Developer Mode")

    def test_feat_0268_is_not_customer_enabled(self):
        row = self._registry_row("FEAT-0268")
        self.assertEqual(row["edition_availability"], "Founder")

    def test_feat_0268_does_not_include_web_ios_android_runtimes(self):
        row = self._registry_row("FEAT-0268")
        self.assertNotIn("Web", row["platform_availability"])
        self.assertNotIn("iOS", row["platform_availability"])
        self.assertNotIn("Android", row["platform_availability"])

    def test_feat_0268_contains_repository_allowlist_language(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-21-SecurityDeviceTrust/DS-021-Security-Device-Trust-Privacy-and-IP-Protection.md",
            "repository allowlist",
        )

    def test_feat_0268_contains_command_limits_language(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-23-Reliability/DS-023-Reliability-Operations-Data-Governance-and-Recovery.md",
            "command count and concurrency",
        )

    def test_feat_0268_contains_resource_limits_language(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-23-Reliability/DS-023-Reliability-Operations-Data-Governance-and-Recovery.md",
            "bounded CPU, memory, disk, process count, and execution time",
        )

    def test_feat_0268_contains_action_logging_language(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-23-Reliability/DS-023-Reliability-Operations-Data-Governance-and-Recovery.md",
            "Action logging",
        )

    def test_feat_0268_contains_no_auto_production_deployment_language(self):
        self._assert_doc_mentions(
            "docs/codex/Volume-18-SageDeployment/DS-018-Sage-Deployment-and-Intelligence-Architecture.md",
            "automatic production deployment",
        )


class TestRejections(RegistryFixtureTestCase):
    def test_duplicate_feature_id_fails(self):
        rows = [_base_row(), _base_row(feature_name="Second row, same ID")]
        self.setup_valid_fixture(rows)
        self.assertIn("unique-feature-ids", self.failing_checks())

    def test_malformed_feature_id_fails(self):
        self.setup_valid_fixture([_base_row(feature_id="FEAT-42")])
        self.assertIn("well-formed-feature-ids", self.failing_checks())

    def test_nonexistent_owner_volume_fails(self):
        self.setup_valid_fixture([_base_row(owner_volume="DS-099")])
        self.assertIn("single-primary-owner", self.failing_checks())

    def test_malformed_owner_volume_fails(self):
        self.setup_valid_fixture([_base_row(owner_volume="DS-2")])
        self.assertIn("single-primary-owner", self.failing_checks())

    def test_invalid_supporting_volume_fails(self):
        self.setup_valid_fixture([_base_row(supporting_volumes="DS-099")])
        self.assertIn("supporting-volumes-valid", self.failing_checks())

    def test_owner_repeated_in_supporting_fails(self):
        self.setup_valid_fixture([_base_row(owner_volume="DS-002", supporting_volumes="DS-002")])
        self.assertIn("supporting-volumes-valid", self.failing_checks())

    def test_unresolved_dependency_fails(self):
        rows = [_base_row(dependencies="FEAT-9999")]
        self.write_registry(rows)
        self.write_dependencies([{
            "feature_id": "FEAT-9001", "feature_name": "Fixture feature",
            "depends_on_feature_id": "FEAT-9999", "depends_on_feature_name": "Missing",
            "dependency_type": "requires", "notes": "",
        }])
        self.write_matrix("PLATFORM_MATRIX_PATH", [self._platform_row(r) for r in rows], vfr.CLIENT_PLATFORMS)
        self.write_matrix("EDITION_MATRIX_PATH", [self._edition_row(r) for r in rows], ("Founder", "Customer"))
        self.write_tradingview("# Fixture\n")
        self.assertIn("dependency-references-resolve", self.failing_checks())

    def test_registry_edge_disagreement_fails(self):
        rows = [_base_row(dependencies="FEAT-9002"), _base_row(feature_id="FEAT-9002")]
        self.write_registry(rows)
        self.write_dependencies([])  # no edges at all -- disagrees with registry column
        self.write_matrix("PLATFORM_MATRIX_PATH", [self._platform_row(r) for r in rows], vfr.CLIENT_PLATFORMS)
        self.write_matrix("EDITION_MATRIX_PATH", [self._edition_row(r) for r in rows], ("Founder", "Customer"))
        self.write_tradingview("# Fixture\n")
        self.assertIn("registry-dependencies-column-synchronized", self.failing_checks())

    def test_missing_platform_row_fails(self):
        rows = self.setup_valid_fixture()
        self.write_matrix("PLATFORM_MATRIX_PATH", [], vfr.CLIENT_PLATFORMS)
        self.assertIn("platform-matrix-one-row-per-feature", self.failing_checks())

    def test_duplicate_platform_row_fails(self):
        rows = self.setup_valid_fixture()
        prow = self._platform_row(rows[0])
        self.write_matrix("PLATFORM_MATRIX_PATH", [prow, dict(prow)], vfr.CLIENT_PLATFORMS)
        self.assertIn("platform-matrix-one-row-per-feature", self.failing_checks())

    def test_platform_registry_disagreement_fails(self):
        rows = self.setup_valid_fixture([_base_row(platform_availability="Windows")])
        prow = self._platform_row(rows[0])
        prow["Web"] = "Yes"  # registry only says Windows
        self.write_matrix("PLATFORM_MATRIX_PATH", [prow], vfr.CLIENT_PLATFORMS)
        self.assertIn("platform-matrix-agrees-with-registry", self.failing_checks())

    def test_missing_edition_row_fails(self):
        rows = self.setup_valid_fixture()
        self.write_matrix("EDITION_MATRIX_PATH", [], ("Founder", "Customer"))
        self.assertIn("edition-matrix-one-row-per-feature", self.failing_checks())

    def test_founder_only_enabled_for_customer_fails(self):
        rows = self.setup_valid_fixture([_base_row(edition_availability="Founder")])
        erow = self._edition_row(rows[0])
        erow["Customer"] = "Yes"  # registry says Founder-only
        self.write_matrix("EDITION_MATRIX_PATH", [erow], ("Founder", "Customer"))
        self.assertIn("edition-matrix-agrees-with-registry", self.failing_checks())

    def test_initial_release_idea_fails(self):
        self.setup_valid_fixture([_base_row(initial_release_required="Yes", implementation_status="Idea")])
        self.assertIn("initial-release-required-not-idea-or-future", self.failing_checks())

    def test_initial_release_future_without_explanation_fails(self):
        self.setup_valid_fixture([_base_row(initial_release_required="Yes", implementation_status="Future",
                                             blocker="None", deprecation_notes="")])
        self.assertIn("initial-release-required-not-idea-or-future", self.failing_checks())

    def test_implemented_without_evidence_fails(self):
        self.setup_valid_fixture([_base_row(implementation_status="Implemented", implementation_evidence="None")])
        self.assertIn("status-evidence-discipline", self.failing_checks())

    def test_tested_without_test_evidence_fails(self):
        self.setup_valid_fixture([_base_row(
            implementation_status="Tested",
            implementation_evidence="backend/app/fixture.py",
            test_evidence="None",
        )])
        self.assertIn("status-evidence-discipline", self.failing_checks())

    def test_released_without_release_evidence_fails(self):
        self.setup_valid_fixture([_base_row(
            implementation_status="Released",
            implementation_evidence="backend/app/fixture.py",
            test_evidence="tests/test_fixture.py",
            release_evidence="None -- not released",
        )])
        self.assertIn("status-evidence-discipline", self.failing_checks())

    def test_placeholder_acceptance_on_safety_critical_fails(self):
        self.setup_valid_fixture([_base_row(
            safety_classification="Deterministic-Authoritative",
            acceptance_summary="TBD -- requirement not yet fully drafted",
        )])
        self.assertIn("no-placeholder-acceptance-on-committed-or-safety-critical", self.failing_checks())

    def test_placeholder_acceptance_on_initial_release_required_fails(self):
        self.setup_valid_fixture([_base_row(
            initial_release_required="Yes",
            implementation_status="Planned",
            acceptance_summary="TBD -- requirement not yet fully drafted",
        )])
        self.assertIn("no-placeholder-acceptance-on-committed-or-safety-critical", self.failing_checks())

    def test_self_referential_design_evidence_fails(self):
        self.setup_valid_fixture([_base_row(design_evidence="This registry entry (Product Expansion foundation pass)")])
        self.assertIn("no-self-referential-design-evidence", self.failing_checks())

    def test_rejected_feature_marked_planned_fails(self):
        self.setup_valid_fixture([_base_row(
            groundwork_required_now="Explicitly Rejected",
            implementation_status="Planned",
        )])
        self.assertIn("explicitly-rejected-not-active", self.failing_checks())

    def test_tradingview_class_a_with_initial_release_no_fails(self):
        self.setup_valid_fixture([_base_row(initial_release_required="No")])
        self.write_tradingview(
            "# Fixture\n\n| Cap | Class | feature_id | Notes |\n|---|---|---|---|\n"
            "| Fixture cap | A | FEAT-9001 | wrong class |\n"
        )
        self.assertIn("tradingview-classification-agrees-with-registry", self.failing_checks())

    def test_tradingview_class_c_without_groundwork_required_now_fails(self):
        self.setup_valid_fixture([_base_row(groundwork_required_now="Decision Pending")])
        self.write_tradingview(
            "# Fixture\n\n| Cap | Class | feature_id | Notes |\n|---|---|---|---|\n"
            "| Fixture cap | C | FEAT-9001 | wrong class |\n"
        )
        self.assertIn("tradingview-classification-agrees-with-registry", self.failing_checks())

    def test_tradingview_class_d_with_groundwork_required_now_and_no_exception_fails(self):
        self.setup_valid_fixture([_base_row(groundwork_required_now="Groundwork Required Now")])
        self.write_tradingview(
            "# Fixture\n\n| Cap | Class | feature_id | Notes |\n|---|---|---|---|\n"
            "| Fixture cap | D | FEAT-9001 | wrong class |\n"
        )
        self.assertIn("tradingview-classification-agrees-with-registry", self.failing_checks())

    def test_founder_local_sage_assigned_web_mobile_runtime_fails(self):
        self.setup_valid_fixture([_base_row(
            feature_id="FEAT-0122", feature_name="Founder Local Sage",
            edition_availability="Founder", platform_availability="Windows;Web;iOS",
        )])
        self.assertIn("founder-customer-edition-separation", self.failing_checks())

    def test_exit_management_feature_missing_safety_classification_fails(self):
        self.setup_valid_fixture([_base_row(category=vfr.EXIT_MANAGEMENT_CATEGORY, safety_classification="N/A")])
        self.assertIn("exit-management-safety-classification", self.failing_checks())

    def test_applicable_exit_feature_missing_ds023_dependency_fails(self):
        # Use a real hard-coded production ID from REQUIRES_DS023 with the
        # dependency deliberately absent.
        fid = sorted(vfr.REQUIRES_DS023)[0]
        self.setup_valid_fixture([_base_row(
            feature_id=fid, category=vfr.EXIT_MANAGEMENT_CATEGORY,
            safety_classification="Deterministic-Authoritative",
            owner_volume="DS-020", supporting_volumes="",
        )])
        self.assertIn("exit-management-ds023-dependency", self.failing_checks())


if __name__ == "__main__":
    unittest.main()
