from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def finalize_evidence(directory: Path, report: dict[str, Any]) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "final-report.json"
    markdown_path = directory / "final-report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    files = []
    for path in sorted(file for file in directory.rglob("*") if file.is_file()):
        if path.name == "evidence-index.json":
            continue
        files.append(
            {
                "path": path.relative_to(directory).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            }
        )
    index = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "files": files,
    }
    (directory / "evidence-index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True), encoding="utf-8"
    )
    return index


def verify_evidence(directory: Path) -> None:
    index = json.loads((directory / "evidence-index.json").read_text(encoding="utf-8"))
    for item in index["files"]:
        path = (directory / item["path"]).resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise RuntimeError("evidence index contains an unsafe or missing file")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError(f"evidence tampering detected: {item['path']}")


def render_markdown(report: dict[str, Any]) -> str:
    sections = ["# Keeper Run Report", ""]
    for key in (
        "objective",
        "repository",
        "worktree",
        "branch",
        "baseline",
        "scope",
        "providers",
        "routing_decisions",
        "authorizations",
        "commands",
        "findings",
        "repairs",
        "verification_results",
        "test_totals",
        "approval_result",
        "git_result",
        "unresolved_observations",
        "evidence_paths",
        "start_time",
        "end_time",
        "terminal_status",
    ):
        sections.extend(
            [f"## {key.replace('_', ' ').title()}", "", "```json", json.dumps(report.get(key), indent=2), "```", ""]
        )
    return "\n".join(sections)
