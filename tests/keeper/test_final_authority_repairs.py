from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from keeper.app.service import KeeperApplication
from keeper.cli import main
from keeper.providers.adapters import (
    ProviderCapabilities,
    ProviderDiagnostic,
    ProviderDiscovery,
    RoutingRequest,
    canonical_provider_registration_digest,
    create_provider_registration,
    route_provider,
)


def _version_script(path: Path, marker: Path, *, success: bool = True) -> None:
    path.write_text(
        "\n".join(
            [
                "@echo off",
                f'echo invoked>>"{marker}"',
                "echo protected-version 1.0" if success else "echo invalid 1>&2",
                "exit /b 0" if success else "exit /b 1",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_registration_creation_cannot_fabricate_qualification(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "provider.cmd"
    marker = tmp_path / "marker.txt"
    _version_script(executable, marker)

    creator: Any = create_provider_registration
    with pytest.raises(TypeError):
        creator(
            "codex",
            executable,
            authorized_by="registrar",
            qualified_version="fabricated 9.9",
        )
    registration = create_provider_registration(
        "codex", executable, authorized_by="registrar"
    )

    assert marker.exists() is False
    assert registration["registration_lifecycle"] == "REGISTERED_UNQUALIFIED"
    assert registration["qualified_version"] is None
    assert registration["qualification_timestamp"] is None
    assert registration["qualification_evidence_id"] is None


def test_protected_qualification_records_actual_output(
    tmp_path: Path,
) -> None:
    app = KeeperApplication(tmp_path / "data")
    executable = tmp_path / "provider.cmd"
    marker = tmp_path / "marker.txt"
    _version_script(executable, marker)
    app.save_provider_paths({"codex": str(executable)})
    app.register_provider("codex", executable, "registrar")

    before = next(
        item for item in app.diagnostics()["providers"] if item["provider_id"] == "codex"
    )
    qualified = app.qualify_provider("codex", "qualifier")
    after = next(
        item for item in app.diagnostics()["providers"] if item["provider_id"] == "codex"
    )

    assert before["discovery_state"] == "registered-unqualified"
    assert before["version"] is None
    assert marker.read_text(encoding="utf-8").count("invoked") == 1
    assert qualified["qualified_version"] == "protected-version 1.0"
    assert qualified["qualification_evidence_id"]
    assert after["discovery_state"] == "qualified"
    assert after["version"] == "protected-version 1.0"


def test_failed_protected_qualification_stays_unqualified(tmp_path: Path) -> None:
    app = KeeperApplication(tmp_path / "data")
    executable = tmp_path / "provider.cmd"
    marker = tmp_path / "marker.txt"
    _version_script(executable, marker, success=False)
    app.save_provider_paths({"codex": str(executable)})
    app.register_provider("codex", executable, "registrar")

    with pytest.raises(PermissionError, match="failed"):
        app.qualify_provider("codex", "qualifier")

    failed = app.provider_registrations()["codex"]
    assert failed["registration_lifecycle"] == "QUALIFICATION_FAILED"
    assert failed["qualified_version"] is None
    diagnostic = next(
        item for item in app.diagnostics()["providers"] if item["provider_id"] == "codex"
    )
    assert diagnostic["discovery_state"] == "qualification-failed"


def test_standalone_batch_uses_composite_qualified_registration(
    tmp_path: Path,
) -> None:
    authority = KeeperApplication(tmp_path / "authority")
    executable = tmp_path / "provider.cmd"
    marker = tmp_path / "marker.txt"
    _version_script(executable, marker)
    authority.register_provider("codex", executable, "registrar")
    registration = authority.qualify_provider("codex", "qualifier")
    evidence = authority.qualification_evidence()[
        str(registration["qualification_evidence_id"])
    ]
    repository = tmp_path / "repository"
    state = repository / ".ai-workflow"
    state.mkdir(parents=True)
    (state / "config.json").write_text(
        json.dumps(
            {
                "provider_command": [str(executable), "{prompt}"],
                "provider_registration": registration,
                "provider_qualification_evidence": evidence,
            }
        ),
        encoding="utf-8",
    )

    assert main(["--root", str(repository), "run-next"]) == 0


@pytest.mark.parametrize(
    ("capabilities", "roles", "requested"),
    [
        (ProviderCapabilities(reviewer=False), ["builder", "repairer"], "reviewer"),
        (ProviderCapabilities(), [], "builder"),
        (ProviderCapabilities(), ["builder"], "reviewer"),
        (ProviderCapabilities(), ["reviewer"], "builder"),
        (ProviderCapabilities(repairer=False), ["builder"], "repairer"),
    ],
)
def test_registered_role_restrictions_prevent_routing(
    capabilities: ProviderCapabilities,
    roles: list[str],
    requested: str,
) -> None:
    diagnostic = ProviderDiagnostic(
        "codex",
        "controlled",
        True,
        "C:\\controlled.exe",
        "1.0",
        "verified",
        capabilities,
        registration={"protected": True},
        discovery_state="qualified",
        role_eligibility=tuple(roles),
        independence_classification="independent-capable",
        provider_policy="registered-command",
    )

    with pytest.raises(RuntimeError):
        route_provider(RoutingRequest(requested, "high", "keeper"), [diagnostic])


def test_discovery_preserves_all_disabled_capabilities_and_empty_roles(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "provider.exe"
    executable.write_bytes(b"provider")
    disabled = ProviderCapabilities(
        author=False,
        reviewer=False,
        repairer=False,
        structured_output=False,
        streaming=False,
        cancellation=False,
        usage_reporting=False,
        local_only=False,
    )
    registration = create_provider_registration(
        "codex",
        executable,
        authorized_by="registrar",
        capabilities=disabled,
        role_eligibility=[],
        independence_classification="authoring-only",
    )

    diagnostic = ProviderDiscovery(
        {"codex": str(executable)}, {"codex": registration}
    ).discover()[0]

    assert diagnostic.available is True
    assert diagnostic.capabilities == disabled
    assert diagnostic.role_eligibility == ()
    with pytest.raises(RuntimeError):
        route_provider(RoutingRequest("reviewer", "high", "keeper"), [diagnostic])


def test_unknown_duplicate_and_inconsistent_roles_are_rejected(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "provider.exe"
    executable.write_bytes(b"provider")
    variants = [
        create_provider_registration(
            "codex", executable, authorized_by="registrar"
        ),
        create_provider_registration(
            "codex", executable, authorized_by="registrar"
        ),
        create_provider_registration(
            "codex", executable, authorized_by="registrar"
        ),
    ]
    variants[0]["role_eligibility"] = ["unknown"]
    variants[1]["role_eligibility"] = ["builder", "builder"]
    variants[2]["capability_set"]["reviewer"] = False
    for registration in variants:
        registration["configuration_digest"] = canonical_provider_registration_digest(
            registration
        )
        diagnostic = ProviderDiscovery(
            {"codex": str(executable)}, {"codex": registration}
        ).discover()[0]
        assert diagnostic.available is False
