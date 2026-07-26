from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from keeper.app.service import KeeperApplication
from keeper.app.workflow import _mock_routes, _routing_digest
from keeper.providers.base import AgentProvider
from keeper.providers.mock import MockProvider


def _state(
    app: KeeperApplication,
) -> tuple[
    str,
    dict[str, object],
    dict[str, AgentProvider],
    list[dict[str, object]],
]:
    run_id = "run-routing"
    task: dict[str, object] = {
        "id": "task-routing",
        "repository": str(app.data_directory),
        "provider_policy": "mock",
    }
    app.store.upsert("tasks", "task-routing", task)
    app.lifecycle.create(run_id, "task-routing")
    providers, _, decisions = _mock_routes("no-repair")
    app.workflow._record_routing_attempt(
        run_id, task, providers, decisions, None, None
    )
    stored_run = app.store.get("runs", run_id)
    assert stored_run is not None
    stored_run["status"] = "blocked"
    stored_run["stopped_from"] = "author_execution"
    app.store.upsert("runs", run_id, stored_run)
    return run_id, task, providers, decisions


def test_retry_reuses_exact_provider_instances_despite_new_instances(
    tmp_path: Path,
) -> None:
    app = KeeperApplication(tmp_path / "data")
    run_id, task, _, previous = _state(app)
    proposed_providers, _, proposed = _mock_routes("no-repair")
    rebound, decisions, authorization = app.workflow._bind_retry_routing(
        run_id,
        task,
        "author_execution",
        proposed_providers,
        proposed,
        None,
    )
    assert authorization is None
    previous_instances = {
        str(item["role"]): str(item["provider_instance_id"])
        for item in previous
    }
    assert {
        str(item["role"]): str(item["provider_instance_id"])
        for item in decisions
    } == previous_instances
    assert rebound["builder"].instance_id == previous_instances["builder"]


def test_changed_unavailable_or_mock_downgrade_blocks_without_reroute(
    tmp_path: Path,
) -> None:
    app = KeeperApplication(tmp_path / "data")
    run_id, task, _, _ = _state(app)
    proposed_providers, _, proposed = _mock_routes("no-repair")
    proposed[0] = {
        **proposed[0],
        "provider_id": "replacement",
        "provider": "replacement",
    }
    proposed_providers["builder"] = MockProvider(provider_name="replacement")
    with pytest.raises(PermissionError, match="reroute authorization"):
        app.workflow._bind_retry_routing(
            run_id,
            task,
            "author_execution",
            proposed_providers,
            proposed,
            None,
        )

    real_task = {**task, "provider_policy": "automatic"}
    prior = [{**item, "policy": "automatic"} for item in proposed]
    run = app.store.get("runs", run_id)
    assert run is not None
    run["routing_attempts"][-1]["provider_policy"] = "automatic"
    run["routing_attempts"][-1]["decisions"] = prior
    app.store.upsert("runs", run_id, run)
    mock_providers, _, mock_decisions = _mock_routes("no-repair")
    with pytest.raises(PermissionError, match="mock"):
        app.workflow._bind_retry_routing(
            run_id,
            real_task,
            "author_execution",
            mock_providers,
            mock_decisions,
            "unused",
        )


def test_explicit_reroute_is_consumed_and_persisted_per_attempt(
    tmp_path: Path,
) -> None:
    app = KeeperApplication(tmp_path / "data")
    run_id, task, _, previous = _state(app)
    proposed_providers, _, proposed = _mock_routes("no-repair")
    proposed[0] = {
        **proposed[0],
        "provider_id": "authorized-replacement",
        "provider": "authorized-replacement",
    }
    proposed_providers["builder"] = MockProvider(
        provider_name="authorized-replacement"
    )
    authorization_id = "authorization-reroute"
    app.store.upsert(
        "authorizations",
        authorization_id,
        {
            "id": authorization_id,
            "capability": "provider_reroute",
            "task_id": "task-routing",
            "run_id": run_id,
            "repository": str(app.data_directory.resolve()),
            "retry_stage": "author_execution",
            "provider_policy": "mock",
            "from_routing_digest": _routing_digest(previous),
            "to_routing_digest": _routing_digest(proposed),
            "approving_authority": "operator",
            "issued_at": datetime.now(UTC).isoformat(),
            "expires_at": (
                datetime.now(UTC) + timedelta(minutes=5)
            ).isoformat(),
            "consumed_at": None,
            "revoked_at": None,
        },
    )
    rebound, decisions, used = app.workflow._bind_retry_routing(
        run_id,
        task,
        "author_execution",
        proposed_providers,
        proposed,
        authorization_id,
    )
    assert used == authorization_id
    consumed = app.store.get("authorizations", authorization_id)
    assert consumed is not None and consumed["consumed_at"]
    app.workflow._record_routing_attempt(
        run_id,
        task,
        rebound,
        decisions,
        "author_execution",
        used,
    )
    persisted = app.store.get("runs", run_id)
    assert persisted is not None
    assert len(persisted["routing_attempts"]) == 2
    latest = persisted["routing_attempts"][-1]
    assert latest["reroute_authorization_id"] == authorization_id
    assert latest["decisions"][0]["provider"] == "authorized-replacement"
    assert persisted["routing_decisions"][0]["provider"] == (
        "authorized-replacement"
    )
    app.workflow._finalize_report(
        run_id,
        task,
        None,
        "BLOCKED",
    )
    report = json.loads(
        (
            app.data_directory / "evidence" / run_id / "final-report.json"
        ).read_text(encoding="utf-8")
    )
    assert report["routing_attempts"][-1]["decisions"][0]["provider"] == (
        "authorized-replacement"
    )


def test_missing_or_malformed_retry_routing_state_fails_closed(
    tmp_path: Path,
) -> None:
    app = KeeperApplication(tmp_path / "data")
    run_id = "run-malformed-routing"
    task: dict[str, object] = {
        "id": "task-routing",
        "repository": str(app.data_directory),
        "provider_policy": "mock",
    }
    app.store.upsert("tasks", "task-routing", task)
    app.lifecycle.create(run_id, "task-routing")
    providers, _, decisions = _mock_routes("no-repair")
    with pytest.raises(PermissionError, match="missing or malformed"):
        app.workflow._bind_retry_routing(
            run_id,
            task,
            "author_execution",
            providers,
            decisions,
            None,
        )
