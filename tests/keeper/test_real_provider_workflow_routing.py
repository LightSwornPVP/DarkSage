from __future__ import annotations

from pathlib import Path

import pytest

from keeper.app import workflow
from keeper.providers.adapters import (
    ProviderCapabilities,
    ProviderDiagnostic,
    ProviderDiscovery,
)


def diagnostic(identifier: str, root: Path) -> ProviderDiagnostic:
    executable = root / f"{identifier}.exe"
    executable.write_bytes(f"controlled {identifier}".encode())
    return ProviderDiagnostic(
        identifier,
        identifier,
        True,
        str(executable),
        "test",
        "controlled fake executable",
        ProviderCapabilities(),
    )


def test_automatic_policy_routes_independent_command_adapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProviderDiscovery,
        "discover",
        lambda self: [diagnostic("codex", tmp_path), diagnostic("claude", tmp_path)],
    )
    providers, routes, decisions = workflow._select_routes(  # noqa: SLF001
        {"provider_policy": "automatic", "risk": "high"}, {}
    )
    assert providers[routes["builder"]].instance_id != providers[routes["reviewer"]].instance_id
    assert {item["role"] for item in decisions} == {
        "builder",
        "reviewer",
        "repairer",
        "post_repair_reviewer",
    }
    assert all(item["policy"] == "automatic" for item in decisions)


def test_automatic_policy_blocks_without_independent_reviewer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProviderDiscovery,
        "discover",
        lambda self: [diagnostic("codex", tmp_path)],
    )
    with pytest.raises(RuntimeError, match="independent"):
        workflow._select_routes(  # noqa: SLF001
            {"provider_policy": "automatic", "risk": "high"}, {}
        )
