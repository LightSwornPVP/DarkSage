"""Unit tests for scripts/publication/*.py.

Every filesystem-dependent test operates inside a throwaway tempfile.
TemporaryDirectory tree with _repo.REPO_ROOT monkeypatched to point at it —
nothing here reads or writes the actual repository tree, and no test depends
on this specific machine's Git state beyond what it explicitly mocks.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _repo  # noqa: E402
import checksum_artifacts  # noqa: E402
import generate_manifest  # noqa: E402
import record_baseline  # noqa: E402
import validate_publication as vp  # noqa: E402


class RepoFixtureTestCase(unittest.TestCase):
    """Base class: builds a minimal fake repo tree and points _repo.REPO_ROOT
    at it for the duration of each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "docs" / "publication").mkdir(parents=True)
        (self.root / "docs" / "requirements").mkdir(parents=True)
        (self.root / "docs" / "publication" / "diagrams" / "source").mkdir(parents=True)
        (self.root / "scripts" / "publication").mkdir(parents=True)

        self._patcher = mock.patch.object(_repo, "REPO_ROOT", self.root)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    def write(self, rel_path: str, content: str) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p


# ---------------------------------------------------------------------------
# checksum_artifacts.py
# ---------------------------------------------------------------------------

class TestChecksumArtifacts(RepoFixtureTestCase):
    def test_existing_file_gets_real_sha256(self):
        p = self.write("docs/publication/sample.md", "hello world\n")
        import hashlib
        expected = hashlib.sha256(p.read_bytes()).hexdigest()

        results = checksum_artifacts.checksum_paths(["docs/publication/sample.md"])

        self.assertTrue(results["docs/publication/sample.md"]["exists"])
        self.assertEqual(results["docs/publication/sample.md"]["sha256"], expected)

    def test_nonexistent_file_never_fabricates_a_checksum(self):
        results = checksum_artifacts.checksum_paths(["docs/publication/does-not-exist.md"])

        self.assertFalse(results["docs/publication/does-not-exist.md"]["exists"])
        self.assertIsNone(results["docs/publication/does-not-exist.md"]["sha256"])

    def test_cli_exits_nonzero_when_any_path_missing(self):
        self.write("docs/publication/real.md", "x")
        rc = checksum_artifacts.main(["docs/publication/real.md", "docs/publication/missing.md", "--json"])
        self.assertEqual(rc, 2)


# ---------------------------------------------------------------------------
# record_baseline.py / _repo.git_head
# ---------------------------------------------------------------------------

class TestBaselineDetection(RepoFixtureTestCase):
    def test_git_head_success(self):
        fake_result = mock.Mock(returncode=0, stdout="abc123def456\n", stderr="")
        with mock.patch.object(_repo.subprocess, "run", return_value=fake_result):
            head = _repo.git_head(self.root)
        self.assertEqual(head, "abc123def456")

    def test_git_head_raises_clearly_when_git_fails(self):
        fake_result = mock.Mock(returncode=128, stdout="", stderr="fatal: not a git repository")
        with mock.patch.object(_repo.subprocess, "run", return_value=fake_result):
            with self.assertRaises(_repo.GitUnavailableError):
                _repo.git_head(self.root)

    def test_git_head_raises_clearly_when_git_not_installed(self):
        with mock.patch.object(_repo.subprocess, "run", side_effect=FileNotFoundError("git not found")):
            with self.assertRaises(_repo.GitUnavailableError):
                _repo.git_head(self.root)

    def test_record_baseline_never_hardcodes_a_commit(self):
        fake_result = mock.Mock(returncode=0, stdout="deadbeef00\n", stderr="")
        with mock.patch.object(_repo.subprocess, "run", return_value=fake_result):
            record = record_baseline.record_baseline()
        self.assertEqual(record["baseline_commit"], "deadbeef00")

    def test_record_baseline_cli_fails_clearly_without_git(self):
        with mock.patch.object(_repo.subprocess, "run", side_effect=FileNotFoundError("no git")):
            rc = record_baseline.main([])
        self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# validate_publication.py — DSF ID uniqueness
# ---------------------------------------------------------------------------

class TestDsfIdUniqueness(RepoFixtureTestCase):
    def test_unique_ids_pass(self):
        self.write("docs/publication/a.md", "# DSF-001 — Alpha\n\nbody\n")
        self.write("docs/publication/b.md", "# DSF-002 — Beta\n\nbody\n")
        report = vp.Report()
        vp.check_dsf_id_uniqueness(report)
        self.assertFalse(report.has_failures)

    def test_duplicate_id_fails(self):
        self.write("docs/publication/a.md", "# DSF-001 — Alpha\n\nbody\n")
        self.write("docs/publication/duplicate.md", "# DSF-001 — Also Alpha\n\nbody\n")
        report = vp.Report()
        vp.check_dsf_id_uniqueness(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any("DSF-001" in f.message for f in report.findings if f.severity == "FAIL"))


# ---------------------------------------------------------------------------
# validate_publication.py — relative links
# ---------------------------------------------------------------------------

class TestRelativeLinks(RepoFixtureTestCase):
    def test_resolving_link_passes(self):
        self.write("docs/publication/target.md", "# Target\n")
        self.write("docs/publication/source.md", "# Source\n\nSee [Target](target.md).\n")
        report = vp.Report()
        vp.check_relative_links(report)
        self.assertFalse(report.has_failures)

    def test_broken_link_fails(self):
        self.write("docs/publication/source.md", "# Source\n\nSee [Missing](nonexistent.md).\n")
        report = vp.Report()
        vp.check_relative_links(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any("nonexistent.md" in f.message for f in report.findings if f.severity == "FAIL"))


# ---------------------------------------------------------------------------
# validate_publication.py — Diagram Register path truthfulness
# ---------------------------------------------------------------------------

class TestDiagramPathTruthfulness(RepoFixtureTestCase):
    def _register_header(self):
        return (
            "| # | Diagram | Purpose | Source Volumes | Authoritative Labels | "
            "Placement(s) | Type | Accessibility Text Requirement | Diagram Standard Class | "
            "Source Path | Rendered Path | Status |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        )

    def test_authored_row_with_missing_source_file_fails(self):
        row = (
            "| 1 | X | p | sv | al | pl | Normative | acc | Component | "
            "`docs/publication/diagrams/source/figure-01-x.mmd` | Pending / Not Yet Rendered | "
            "Authored (source only, not rendered) |\n"
        )
        self.write("docs/publication/DIAGRAM_REGISTER.md", "# Register\n\n" + self._register_header() + row)

        report = vp.Report()
        rows = vp.check_diagram_register_schema(report)
        vp.check_diagram_path_truthfulness(report, rows)

        self.assertTrue(any(
            "does not exist on disk" in f.message
            for f in report.findings if f.severity == "FAIL"
        ))

    def test_authored_row_with_real_source_file_passes(self):
        self.write("docs/publication/diagrams/source/figure-01-x.mmd", "%% test\n")
        row = (
            "| 1 | X | p | sv | al | pl | Normative | acc | Component | "
            "`docs/publication/diagrams/source/figure-01-x.mmd` | Pending / Not Yet Rendered | "
            "Authored (source only, not rendered) |\n"
        )
        self.write("docs/publication/DIAGRAM_REGISTER.md", "# Register\n\n" + self._register_header() + row)

        report = vp.Report()
        rows = vp.check_diagram_register_schema(report)
        vp.check_diagram_path_truthfulness(report, rows)

        self.assertFalse(any(
            f.check == "diagram-path-truthfulness" and f.severity == "FAIL"
            for f in report.findings
        ))

    def test_rendered_path_claiming_nonexistent_file_fails(self):
        self.write("docs/publication/diagrams/source/figure-01-x.mmd", "%% test\n")
        row = (
            "| 1 | X | p | sv | al | pl | Normative | acc | Component | "
            "`docs/publication/diagrams/source/figure-01-x.mmd` | "
            "`docs/publication/diagrams/rendered/figure-01-x.svg` | "
            "Authored |\n"
        )
        self.write("docs/publication/DIAGRAM_REGISTER.md", "# Register\n\n" + self._register_header() + row)

        report = vp.Report()
        rows = vp.check_diagram_register_schema(report)
        vp.check_diagram_path_truthfulness(report, rows)

        self.assertTrue(any(
            "Rendered Path cell names a file that does not exist" in f.message
            for f in report.findings if f.severity == "FAIL"
        ))


# ---------------------------------------------------------------------------
# validate_publication.py — accessibility descriptions
# ---------------------------------------------------------------------------

class TestAccessibilityDescriptions(RepoFixtureTestCase):
    def test_missing_accessibility_text_fails(self):
        self.write("docs/publication/diagrams/source/figure-99-nodesc.mmd", "graph TD\nA-->B\n")
        report = vp.Report()
        vp.check_accessibility_descriptions(report)
        self.assertTrue(report.has_failures)

    def test_present_accessibility_text_passes(self):
        content = (
            "%% Accessibility description (full sentence form): this diagram shows a very "
            "simple two node relationship used purely to validate the accessibility check "
            "logic in the publication tooling test suite, with enough words to pass the "
            "minimum length heuristic used by the checker.\n"
            "graph TD\nA-->B\n"
        )
        self.write("docs/publication/diagrams/source/figure-98-desc.mmd", content)
        report = vp.Report()
        vp.check_accessibility_descriptions(report)
        self.assertFalse(any(
            f.check == "accessibility-descriptions" and f.severity == "FAIL"
            for f in report.findings
        ))


# ---------------------------------------------------------------------------
# validate_publication.py — manifest checks
# ---------------------------------------------------------------------------

VALID_ENTRY_TEMPLATE = {
    "document_id": "DSF-999",
    "title": "Test Doc",
    "source_path": "docs/publication/test.md",
    "source_version": "0.1.0",
    "source_status": "Draft",
    "source_baseline": "deadbeef",
    "artifact_type": "docx",
    "planned_artifact_path": "docs/publication/releases/DSF-999.docx",
    "generated": False,
    "generation_timestamp": None,
    "checksum": None,
    "generator_version": None,
    "notes": "not generated",
}


class TestManifestChecks(RepoFixtureTestCase):
    def test_valid_manifest_passes(self):
        manifest = {
            "manifest_schema_version": "1.0.0",
            "baseline_commit": "deadbeef",
            "entries": [dict(VALID_ENTRY_TEMPLATE)],
        }
        self.write("docs/publication/PUBLICATION_MANIFEST.json", json.dumps(manifest))

        report = vp.Report()
        data = vp.check_manifest_json(report)
        vp.check_manifest_generated_truthfulness(report, data)

        self.assertFalse(report.has_failures)

    def test_generated_true_for_missing_file_fails(self):
        entry = dict(VALID_ENTRY_TEMPLATE)
        entry["generated"] = True
        entry["checksum"] = "somefakehash"
        manifest = {
            "manifest_schema_version": "1.0.0",
            "baseline_commit": "deadbeef",
            "entries": [entry],
        }
        self.write("docs/publication/PUBLICATION_MANIFEST.json", json.dumps(manifest))

        report = vp.Report()
        data = vp.check_manifest_json(report)
        vp.check_manifest_generated_truthfulness(report, data)

        self.assertTrue(any(
            "does not exist on disk" in f.message
            for f in report.findings if f.severity == "FAIL"
        ))

    def test_generated_true_with_real_file_and_correct_checksum_passes(self):
        artifact_rel = "docs/publication/releases/DSF-999.docx"
        p = self.write(artifact_rel, "fake docx bytes")
        real_checksum = _repo.sha256_of_file(p)

        entry = dict(VALID_ENTRY_TEMPLATE)
        entry["generated"] = True
        entry["checksum"] = real_checksum
        manifest = {
            "manifest_schema_version": "1.0.0",
            "baseline_commit": "deadbeef",
            "entries": [entry],
        }
        self.write("docs/publication/PUBLICATION_MANIFEST.json", json.dumps(manifest))

        report = vp.Report()
        data = vp.check_manifest_json(report)
        vp.check_manifest_generated_truthfulness(report, data)

        self.assertFalse(report.has_failures)

    def test_malformed_json_fails(self):
        self.write("docs/publication/PUBLICATION_MANIFEST.json", "{not valid json")
        report = vp.Report()
        data = vp.check_manifest_json(report)
        self.assertIsNone(data)
        self.assertTrue(report.has_failures)


# ---------------------------------------------------------------------------
# validate_publication.py — contrast ratios (pure function, no fixture needed)
# ---------------------------------------------------------------------------

class TestContrastRatios(unittest.TestCase):
    def test_known_repaired_colors_meet_aa(self):
        self.assertGreaterEqual(vp.contrast_ratio("#1E6E43", vp.IVORY_WHITE), 4.5)
        self.assertGreaterEqual(vp.contrast_ratio("#8A6013", vp.IVORY_WHITE), 4.5)

    def test_known_prior_failing_colors_actually_fail(self):
        # The original, pre-repair BRAND_GUIDE.md values — must measure below
        # 4.5:1, confirming the audit finding this repair addresses was real.
        self.assertLess(vp.contrast_ratio("#2E8B57", vp.IVORY_WHITE), 4.5)
        self.assertLess(vp.contrast_ratio("#C58A1B", vp.IVORY_WHITE), 4.5)

    def test_black_on_white_is_maximum_contrast(self):
        self.assertAlmostEqual(vp.contrast_ratio("#000000", "#FFFFFF"), 21.0, places=1)


# ---------------------------------------------------------------------------
# HIGH3 — repository path containment (_repo.resolve_repo_path)
# ---------------------------------------------------------------------------

class TestPathContainment(RepoFixtureTestCase):
    def test_relative_path_inside_repo_succeeds(self):
        self.write("docs/publication/inside.md", "# Inside\n")
        p = _repo.resolve_repo_path("docs/publication/inside.md")
        self.assertTrue(p.is_file())
        self.assertTrue(str(p).startswith(str(self.root)))

    def test_parent_traversal_is_rejected(self):
        with self.assertRaises(_repo.PathContainmentError):
            _repo.resolve_repo_path("../outside.txt")

    def test_nested_traversal_is_rejected(self):
        with self.assertRaises(_repo.PathContainmentError):
            _repo.resolve_repo_path("docs/publication/../../../outside.txt")

    def test_absolute_path_is_rejected(self):
        with self.assertRaises(_repo.PathContainmentError):
            _repo.resolve_repo_path(str(Path(self._tmp.name).anchor) + "some/absolute/path.txt")

    def test_external_temp_file_cannot_be_checksummed(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as external:
            external.write(b"secret outside the repo")
            external_path = external.name
        try:
            results = checksum_artifacts.checksum_paths([external_path])
            info = results[external_path]
            self.assertIsNone(info["sha256"])
            self.assertFalse(info["exists"])
            self.assertIsNotNone(info.get("rejected"))
        finally:
            os.unlink(external_path)

    def test_manifest_output_outside_repo_is_rejected(self):
        with tempfile.TemporaryDirectory() as other_dir:
            outside_target = str(Path(other_dir) / "escaped_manifest.json")
            fake_result = mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
            with mock.patch.object(_repo.subprocess, "run", return_value=fake_result):
                rc = generate_manifest.main(["--output", outside_target])
            self.assertEqual(rc, 1)

    def test_no_external_output_file_created(self):
        with tempfile.TemporaryDirectory() as other_dir:
            outside_target = Path(other_dir) / "should_not_exist.json"
            fake_result = mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
            with mock.patch.object(_repo.subprocess, "run", return_value=fake_result):
                generate_manifest.main(["--output", str(outside_target)])
            self.assertFalse(outside_target.exists())

    def test_valid_in_repo_manifest_output_succeeds(self):
        self.write("docs/publication/DARKSAGE_PUBLICATION_ARCHITECTURE.md", "# DSF-001 — X\n\n| Version | 0.1.0 |\n|---|---|\n")
        fake_result = mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
        with mock.patch.object(_repo.subprocess, "run", return_value=fake_result):
            rc = generate_manifest.main(["--output", "docs/publication/PUBLICATION_MANIFEST.json"])
        self.assertEqual(rc, 0)
        self.assertTrue((self.root / "docs/publication/PUBLICATION_MANIFEST.json").is_file())

    def test_record_baseline_output_outside_repo_is_rejected(self):
        with tempfile.TemporaryDirectory() as other_dir:
            outside_target = str(Path(other_dir) / "baseline.json")
            fake_result = mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
            with mock.patch.object(_repo.subprocess, "run", return_value=fake_result):
                rc = record_baseline.main(["--output", outside_target])
            self.assertEqual(rc, 1)
            self.assertFalse(Path(outside_target).exists())

    def test_symlink_escape_is_rejected_where_supported(self):
        with tempfile.TemporaryDirectory() as other_dir:
            external_file = Path(other_dir) / "external.txt"
            external_file.write_text("outside content")
            link_path = self.root / "docs" / "publication" / "escape_link.txt"
            try:
                os.symlink(external_file, link_path)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("symlinks not supported/permitted in this environment")
            with self.assertRaises(_repo.PathContainmentError):
                _repo.resolve_repo_path("docs/publication/escape_link.txt")


# ---------------------------------------------------------------------------
# HIGH4-A — controlled-ID reference validation
# ---------------------------------------------------------------------------

class TestControlledIdReferences(RepoFixtureTestCase):
    def test_valid_controlled_reference_succeeds(self):
        self.write("docs/codex/Volume-01-Foundation/DS-001-x.md", "# DS-001 — Executive Vision\n")
        self.write("docs/publication/uses.md", "# DSF-100 — Uses\n\nSee DS-001 for background.\n")
        report = vp.Report()
        vp.check_controlled_id_references(report)
        self.assertFalse(report.has_failures)

    def test_unresolved_normative_id_fails(self):
        self.write("docs/publication/uses.md", "# DSF-100 — Uses\n\nSee DS-999 which does not exist anywhere.\n")
        report = vp.Report()
        vp.check_controlled_id_references(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any("DS-999" in f.message for f in report.findings if f.severity == "FAIL"))

    def test_duplicate_dsf_definition_fails(self):
        self.write("docs/publication/a.md", "# DSF-050 — Alpha\n")
        self.write("docs/publication/b.md", "# DSF-050 — Also Alpha\n")
        report = vp.Report()
        vp.check_dsf_id_uniqueness(report)
        self.assertTrue(report.has_failures)

    def test_placeholder_ids_do_not_create_false_definitions_or_references(self):
        # Template-style placeholders (DS-XXX, DS-<DOMAIN>-NNN, ADR-XXX) contain no
        # digits and must never be treated as either a definition or a reference.
        self.write(
            "docs/publication/templates/08-RequirementCard.md",
            "## {{RequirementID}}\n\nControlling Source: DS-XXX-001, ADR-XXX\n",
        )
        self.write("docs/publication/real.md", "# DSF-101 — Real\n\nNo controlled IDs referenced here.\n")
        report = vp.Report()
        vp.check_controlled_id_references(report)
        self.assertFalse(report.has_failures)


# ---------------------------------------------------------------------------
# HIGH4-B — general Markdown-table validation
# ---------------------------------------------------------------------------

class TestMarkdownTableValidation(RepoFixtureTestCase):
    def test_valid_delimiter_passes(self):
        self.write(
            "docs/publication/table.md",
            "# Doc\n\n| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n",
        )
        report = vp.Report()
        vp.check_markdown_tables(report)
        self.assertFalse(report.has_failures)
        self.assertTrue(any(
            f.check == "markdown-table-validation" and f.severity == "OK" and "table.md:3" in f.message
            for f in report.findings
        ))

    def test_delimiter_variants_pass(self):
        for variant in ("---", ":---", "---:", ":---:"):
            with self.subTest(variant=variant):
                self.write(
                    "docs/publication/table.md",
                    f"# Doc\n\n| A |\n|{variant}|\n| 1 |\n",
                )
                report = vp.Report()
                vp.check_markdown_tables(report)
                self.assertFalse(report.has_failures, f"variant {variant!r} should be a valid delimiter cell")

    def test_delimiter_too_few_hyphens_fails(self):
        self.write(
            "docs/publication/table.md",
            "# Doc\n\n| A | B |\n|--|--|\n| 1 | 2 |\n",
        )
        report = vp.Report()
        vp.check_markdown_tables(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any(
            f.severity == "FAIL" and "table.md:4" in f.message and "too few hyphens" in f.message
            for f in report.findings
        ))

    def test_delimiter_invalid_characters_fail(self):
        self.write(
            "docs/publication/table.md",
            "# Doc\n\n| A | B |\n|***|***|\n| 1 | 2 |\n",
        )
        report = vp.Report()
        vp.check_markdown_tables(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any(
            f.severity == "FAIL" and "table.md:4" in f.message and "invalid character" in f.message
            for f in report.findings
        ))

    def test_delimiter_header_width_mismatch_fails(self):
        self.write(
            "docs/publication/table.md",
            "# Doc\n\n| A | B | C |\n|---|---|\n| 1 | 2 | 3 |\n",
        )
        report = vp.Report()
        vp.check_markdown_tables(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any(
            f.severity == "FAIL" and "delimiter row has 2 cell(s), expected 3" in f.message
            for f in report.findings
        ))

    def test_malformed_delimiter_returns_nonzero(self):
        self.write(
            "docs/publication/table.md",
            "# Doc\n\n| A | B |\n|--|--|\n| 1 | 2 |\n",
        )
        report = vp.Report()
        vp.check_markdown_tables(report)
        # Mirrors main()'s own exit-code rule: any FAIL -> nonzero.
        exit_code = 1 if report.has_failures else 0
        self.assertEqual(exit_code, 1)

    def test_inconsistent_row_width_fails(self):
        self.write(
            "docs/publication/table.md",
            "# Doc\n\n| A | B |\n|---|---|\n| 1 | 2 | 3 |\n",
        )
        report = vp.Report()
        vp.check_markdown_tables(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any(
            f.severity == "FAIL" and "table.md:5" in f.message and "3 column(s), expected 2" in f.message
            for f in report.findings
        ))

    def test_unescaped_pipe_fails(self):
        self.write(
            "docs/publication/table.md",
            "# Doc\n\n| A | B |\n|---|---|\n| 1 | a|b |\n",
        )
        report = vp.Report()
        vp.check_markdown_tables(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any(
            f.severity == "FAIL" and "table.md:5" in f.message
            for f in report.findings
        ))

    def test_escaped_pipe_succeeds(self):
        self.write(
            "docs/publication/table.md",
            "# Doc\n\n| A | B |\n|---|---|\n| 1 | a\\|b |\n",
        )
        report = vp.Report()
        vp.check_markdown_tables(report)
        self.assertFalse(report.has_failures)


# ---------------------------------------------------------------------------
# HIGH4-C — Mermaid structural validation
# ---------------------------------------------------------------------------

VALID_MERMAID = (
    "%% Figure 42 — Test Diagram\n"
    "%% Accessibility description (full sentence form): this is a simple two node "
    "diagram used only to validate the Mermaid structural checker's happy path, "
    "with enough descriptive words to satisfy the minimum length heuristic used "
    "by the accessibility checker.\n"
    "graph LR\n"
    "    A[\"Node A\"] --> B[\"Node B\"]\n"
)


class TestMermaidStructuralValidation(RepoFixtureTestCase):
    def test_valid_simple_source_succeeds(self):
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", VALID_MERMAID)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertFalse(report.has_failures)

    def test_unbalanced_brackets_fail(self):
        bad = VALID_MERMAID.replace('A["Node A"] --> B["Node B"]', 'A["Node A" --> B["Node B"]')
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", bad)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(report.has_failures)
        self.assertTrue(any("bracket" in f.message for f in report.findings if f.severity == "FAIL"))

    def test_missing_accessibility_description_fails(self):
        no_a11y = "%% Figure 42 — Test Diagram\ngraph LR\n    A[\"Node A\"] --> B[\"Node B\"]\n"
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", no_a11y)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(any(
            "Accessibility description" in f.message and f.severity == "FAIL"
            for f in report.findings
        ))

    def _register_with_row(self, num: int, source_path: str) -> str:
        header = (
            "| # | Diagram | Purpose | Source Volumes | Authoritative Labels | "
            "Placement(s) | Type | Accessibility Text Requirement | Diagram Standard Class | "
            "Source Path | Rendered Path | Status |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        )
        rows = []
        for n in range(1, 20):
            sp = f"`{source_path}`" if n == num else "Not Yet Authored"
            status = "Authored" if n == num else "Not Yet Authored"
            rows.append(f"| {n} | D{n} | p | sv | al | pl | Normative | acc | Component | {sp} | Pending | {status} |\n")
        return "# Register\n\n" + header + "".join(rows)

    def test_figure5_prohibited_sage_edge_fails(self):
        broken_figure5 = (
            "%% Figure 5 — Sage Advisory Boundary\n"
            "%% Accessibility description: this fixture intentionally reintroduces the "
            "prohibited edge to confirm the semantic scan actually detects it and does "
            "not silently pass a defective diagram through the validator.\n"
            "graph LR\n"
            "    Sage[\"Sage\"] --> Proposal[\"Trade Proposal\"]\n"
            "    Sage -.-> Exec[\"Execution Engine\"]\n"
        )
        self.write("docs/publication/diagrams/source/figure-05-sage-advisory-boundary.mmd", broken_figure5)
        self.write(
            "docs/publication/DIAGRAM_REGISTER.md",
            self._register_with_row(5, "docs/publication/diagrams/source/figure-05-sage-advisory-boundary.mmd"),
        )
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(any(
            "prohibited" in f.message
            for f in report.findings if f.severity == "FAIL"
        ))

    def test_figure5_repaired_passes(self):
        good_figure5 = (
            "%% Figure 5 — Sage Advisory Boundary\n"
            "%% Accessibility description: this fixture uses the repaired boundary-box "
            "representation with no edge from Sage to the Execution Engine or Broker "
            "Adapter, confirming the semantic scan passes a genuinely compliant diagram.\n"
            "graph LR\n"
            "    Sage[\"Sage\"] --> Proposal[\"Trade Proposal\"]\n"
            "    Proposal --> Risk[\"Risk Engine\"]\n"
            "    Risk --> Exec[\"Execution Engine\"]\n"
            "    Exec --> Broker[\"Broker Adapter\"]\n"
        )
        self.write("docs/publication/diagrams/source/figure-05-sage-advisory-boundary.mmd", good_figure5)
        self.write(
            "docs/publication/DIAGRAM_REGISTER.md",
            self._register_with_row(5, "docs/publication/diagrams/source/figure-05-sage-advisory-boundary.mmd"),
        )
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertFalse(any(
            f.check == "mermaid-structural-validation" and f.severity == "FAIL"
            for f in report.findings
        ))

    def test_canonical_pipeline_wrong_order_fails(self):
        self.write("docs/pipeline-stages.txt", "Stage One\nStage Two\nStage Three\n")
        wrong_order = (
            "%% Figure 3 — Canonical Trade Validation Pipeline\n"
            "%% Accessibility description: this fixture intentionally reorders the "
            "canonical pipeline stages to confirm the exact-order comparison actually "
            "detects a reordering rather than silently accepting it.\n"
            "graph LR\n"
            "    S1[\"Stage Two\"] --> S2[\"Stage One\"]\n"
            "    S2 --> S3[\"Stage Three\"]\n"
        )
        self.write("docs/publication/diagrams/source/figure-03-trade-validation-pipeline.mmd", wrong_order)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(any(
            "pipeline stage order does not match" in f.message
            for f in report.findings if f.severity == "FAIL"
        ))

    def test_canonical_pipeline_exact_order_passes(self):
        self.write("docs/pipeline-stages.txt", "Stage One\nStage Two\nStage Three\n")
        right_order = (
            "%% Figure 3 — Canonical Trade Validation Pipeline\n"
            "%% Accessibility description: this fixture uses the exact canonical stage "
            "order to confirm the comparison accepts a genuinely correct, in-order "
            "reproduction of the pipeline.\n"
            "graph LR\n"
            "    S1[\"Stage One\"] --> S2[\"Stage Two\"]\n"
            "    S2 --> S3[\"Stage Three\"]\n"
        )
        self.write("docs/publication/diagrams/source/figure-03-trade-validation-pipeline.mmd", right_order)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(any(
            "pipeline stage order matches" in f.message and f.severity == "OK"
            for f in report.findings
        ))


# ---------------------------------------------------------------------------
# Final-repair section 2 — Mermaid edge-token allowlist (strict, exact-match)
# ---------------------------------------------------------------------------

def _two_node_diagram(arrow: str) -> str:
    return (
        "%% Figure 42 — Test Diagram\n"
        "%% Accessibility description (full sentence form): this fixture exercises a "
        "single edge between two explicitly declared nodes to validate arrow-token "
        "handling in isolation, with enough descriptive words to satisfy the minimum "
        "length heuristic used by the accessibility checker.\n"
        "graph LR\n"
        f'    A["Node A"] {arrow} B["Node B"]\n'
    )


class TestMermaidEdgeTokenAllowlist(RepoFixtureTestCase):
    def test_each_supported_token_passes(self):
        for token in sorted(vp.APPROVED_EDGE_TOKENS):
            with self.subTest(token=token):
                self.write("docs/publication/diagrams/source/figure-42-test.mmd", _two_node_diagram(token))
                report = vp.Report()
                vp.check_mermaid_sources(report)
                self.assertFalse(
                    report.has_failures,
                    f"approved token {token!r} unexpectedly failed: "
                    f"{[f.message for f in report.findings if f.severity == 'FAIL']}",
                )

    def test_unsupported_token_tilde_arrow_fails(self):
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", _two_node_diagram("~~>"))
        report = vp.Report()
        vp.check_mermaid_sources(report)
        exit_code = 1 if report.has_failures else 0
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(
            f.severity == "FAIL" and "unapproved arrow token '~~>'" in f.message and "figure-42-test.mmd:4" in f.message
            for f in report.findings
        ))

    def test_malformed_partial_arrow_fails(self):
        # Two hyphens only — not the three-hyphen '---' plain-edge token, and
        # not a real directional arrow either.
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", _two_node_diagram("--"))
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(any(
            f.severity == "FAIL" and "unapproved arrow token '--'" in f.message
            for f in report.findings
        ))

    def test_unsupported_reverse_arrow_fails(self):
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", _two_node_diagram("<--"))
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(any(
            f.severity == "FAIL" and "unapproved arrow token '<--'" in f.message
            for f in report.findings
        ))

    def test_unsupported_double_equals_bidirectional_fails(self):
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", _two_node_diagram("<==>"))
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(any(
            f.severity == "FAIL" and "unapproved arrow token '<==>'" in f.message
            for f in report.findings
        ))


# ---------------------------------------------------------------------------
# Final-repair section 3 — real declared-node consistency
# ---------------------------------------------------------------------------

class TestDeclaredNodeConsistency(RepoFixtureTestCase):
    def test_two_explicitly_declared_endpoints_pass(self):
        src = (
            "%% Figure 42 — Test Diagram\n"
            "%% Accessibility description: two nodes declared on their own lines before "
            "the edge that connects them, confirming pre-declared bare endpoints pass "
            "the declared-node consistency check without any inline bracket on the edge "
            "line itself.\n"
            "graph LR\n"
            "    A[\"Node A\"]\n"
            "    B[\"Node B\"]\n"
            "    A --> B\n"
        )
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", src)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertFalse(any("undeclared node" in f.message for f in report.findings if f.severity == "FAIL"))

    def test_valid_inline_declarations_pass(self):
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", VALID_MERMAID)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertFalse(any("undeclared node" in f.message for f in report.findings if f.severity == "FAIL"))

    def test_undeclared_source_node_fails(self):
        src = (
            "%% Figure 42 — Test Diagram\n"
            "%% Accessibility description: node A is never declared with a bracket, "
            "paren, or brace anywhere in this file, confirming a bare, never-declared "
            "source endpoint is correctly rejected rather than silently accepted.\n"
            "graph LR\n"
            "    B[\"Node B\"]\n"
            "    A --> B\n"
        )
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", src)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        exit_code = 1 if report.has_failures else 0
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(
            f.severity == "FAIL" and "undeclared node 'A'" in f.message and "figure-42-test.mmd:5" in f.message
            for f in report.findings
        ))

    def test_undeclared_target_node_fails(self):
        src = (
            "%% Figure 42 — Test Diagram\n"
            "%% Accessibility description: node B is never declared with a bracket, "
            "paren, or brace anywhere in this file, confirming a bare, never-declared "
            "target endpoint is correctly rejected rather than silently accepted.\n"
            "graph LR\n"
            "    A[\"Node A\"]\n"
            "    A --> B\n"
        )
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", src)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        self.assertTrue(any(
            f.severity == "FAIL" and "undeclared node 'B'" in f.message
            for f in report.findings
        ))

    def test_edge_use_does_not_itself_declare_a_node(self):
        # 'B' appears as a bare endpoint in two separate edges but is never
        # bracket/paren/brace-declared anywhere — neither mention should
        # "teach" the validator that B exists; both edges must still fail.
        src = (
            "%% Figure 42 — Test Diagram\n"
            "%% Accessibility description: node B appears twice as a bare edge endpoint "
            "and is never declared, confirming that repeated edge use does not silently "
            "establish a declaration for a node that was never actually declared.\n"
            "graph LR\n"
            "    A[\"Node A\"]\n"
            "    C[\"Node C\"]\n"
            "    A --> B\n"
            "    B --> C\n"
        )
        self.write("docs/publication/diagrams/source/figure-42-test.mmd", src)
        report = vp.Report()
        vp.check_mermaid_sources(report)
        undeclared_b_hits = [
            f for f in report.findings
            if f.severity == "FAIL" and "undeclared node 'B'" in f.message
        ]
        self.assertEqual(len(undeclared_b_hits), 2, "both edges referencing bare 'B' must independently fail")


# ---------------------------------------------------------------------------
# Final-repair section 4 — Figure 16 semantic label validation
# ---------------------------------------------------------------------------

def _figure16_source(promotion_edge: str, xref_edge: str) -> str:
    return (
        "%% Figure 16 — DS-013 versus DS-014 Boundary\n"
        "%% Accessibility description: this fixture exercises the Promotion/"
        "Cross-reference label-semantics check in isolation, with enough descriptive "
        "words to satisfy the minimum length heuristic used by the accessibility "
        "checker in this validator.\n"
        "graph LR\n"
        "    subgraph DS014[\"DS-014\"]\n"
        "        Idea[\"Idea\"]\n"
        "    end\n"
        "    subgraph DS013[\"DS-013\"]\n"
        "        Backlog[\"Backlog Item\"]\n"
        "    end\n"
        f"    {promotion_edge}\n"
        f"    {xref_edge}\n"
    )


REPAIRED_PROMOTION_EDGE = 'Idea -->|"Promotion — requires the approved controlling process"| Backlog'
REPAIRED_XREF_EDGE = 'Idea <-.->|"Cross-reference — bidirectional, by ID"| Backlog'


class TestFigure16LabelSemantics(RepoFixtureTestCase):
    def _register_row16(self, source_path: str) -> str:
        header = (
            "| # | Diagram | Purpose | Source Volumes | Authoritative Labels | "
            "Placement(s) | Type | Accessibility Text Requirement | Diagram Standard Class | "
            "Source Path | Rendered Path | Status |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        )
        rows = []
        for n in range(1, 20):
            sp = f"`{source_path}`" if n == 16 else "Not Yet Authored"
            status = "Authored" if n == 16 else "Not Yet Authored"
            rows.append(f"| {n} | D{n} | p | sv | al | pl | Normative | acc | Component | {sp} | Pending | {status} |\n")
        return "# Register\n\n" + header + "".join(rows)

    def _run(self, promotion_edge: str, xref_edge: str) -> vp.Report:
        path = "docs/publication/diagrams/source/figure-16-ds013-vs-ds014-boundary.mmd"
        self.write(path, _figure16_source(promotion_edge, xref_edge))
        self.write("docs/publication/DIAGRAM_REGISTER.md", self._register_row16(path))
        report = vp.Report()
        vp.check_mermaid_sources(report)
        return report

    def test_repaired_figure16_passes(self):
        report = self._run(REPAIRED_PROMOTION_EDGE, REPAIRED_XREF_EDGE)
        self.assertFalse(any(f.check == "mermaid-structural-validation" and f.severity == "FAIL" for f in report.findings))
        self.assertTrue(any(
            f.severity == "OK" and "correctly-labeled one-way Promotion edge" in f.message
            for f in report.findings
        ))

    def test_swapped_labels_fail(self):
        swapped_promo = 'Idea -->|"Cross-reference — requires the approved controlling process"| Backlog'
        swapped_xref = 'Idea <-.->|"Promotion — bidirectional, by ID"| Backlog'
        report = self._run(swapped_promo, swapped_xref)
        exit_code = 1 if report.has_failures else 0
        self.assertEqual(exit_code, 1)
        self.assertTrue(any("incorrectly labeled Cross-reference" in f.message for f in report.findings if f.severity == "FAIL"))
        self.assertTrue(any("incorrectly labeled Promotion" in f.message for f in report.findings if f.severity == "FAIL"))

    def test_missing_promotion_label_fails(self):
        unlabeled_promo = "Idea --> Backlog"
        report = self._run(unlabeled_promo, REPAIRED_XREF_EDGE)
        self.assertTrue(any(
            f.severity == "FAIL" and "expected a 'Promotion' label" in f.message
            for f in report.findings
        ))

    def test_missing_cross_reference_label_fails(self):
        unlabeled_xref = "Idea <-.-> Backlog"
        report = self._run(REPAIRED_PROMOTION_EDGE, unlabeled_xref)
        self.assertTrue(any(
            f.severity == "FAIL" and "expected a 'Cross-reference' label" in f.message
            for f in report.findings
        ))

    def test_reverse_promotion_fails(self):
        reverse_promo = 'Backlog -->|"Promotion — requires the approved controlling process"| Idea'
        report = self._run(reverse_promo, REPAIRED_XREF_EDGE)
        self.assertTrue(any(
            f.severity == "FAIL" and "promotion must never run backward into DS-014" in f.message
            for f in report.findings
        ))

    def test_bidirectional_promotion_fails(self):
        # Only a bidirectional edge exists, carrying the Promotion label —
        # no separate one-way edge at all.
        bidirectional_promo = 'Idea <-.->|"Promotion — requires the approved controlling process"| Backlog'
        path = "docs/publication/diagrams/source/figure-16-ds013-vs-ds014-boundary.mmd"
        self.write(
            path,
            "%% Figure 16 — DS-013 versus DS-014 Boundary\n"
            "%% Accessibility description: this fixture uses only a single bidirectional "
            "edge mislabeled Promotion, with no separate one-way edge, confirming the "
            "bidirectional-promotion defect is rejected rather than silently accepted.\n"
            "graph LR\n"
            "    subgraph DS014[\"DS-014\"]\n"
            "        Idea[\"Idea\"]\n"
            "    end\n"
            "    subgraph DS013[\"DS-013\"]\n"
            "        Backlog[\"Backlog Item\"]\n"
            "    end\n"
            f"    {bidirectional_promo}\n",
        )
        self.write("docs/publication/DIAGRAM_REGISTER.md", self._register_row16(path))
        report = vp.Report()
        vp.check_mermaid_sources(report)
        exit_code = 1 if report.has_failures else 0
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(
            "expected exactly one one-way Idea-->Backlog promotion edge, found 0" in f.message
            for f in report.findings if f.severity == "FAIL"
        ))
        self.assertTrue(any(
            "incorrectly labeled Promotion" in f.message
            for f in report.findings if f.severity == "FAIL"
        ))


if __name__ == "__main__":
    unittest.main()
