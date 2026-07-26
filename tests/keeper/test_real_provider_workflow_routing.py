from __future__ import annotations

import pytest

from keeper.app import workflow
from keeper.providers.adapters import (
    ProviderCapabilities,
    ProviderDiagnostic,
    ProviderDiscovery,
)


def diagnostic(identifier: str) -> ProviderDiagnostic:
    return ProviderDiagnostic(
        identifier,
        identifier,
        True,
        f"C:/{identifier}.exe",
        "test",
        "controlled fake executable",
        ProviderCapabilities(),
    )


def test_automatic_policy_routes_independent_command_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProviderDiscovery,
        "discover",
        lambda self: [diagnostic("codex"), diagnostic("claude")],
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProviderDiscovery, "discover", lambda self: [diagnostic("codex")]
    )
    with pytest.raises(RuntimeError, match="independent"):
        workflow._select_routes(  # noqa: SLF001
            {"provider_policy": "automatic", "risk": "high"}, {}
        )
