from __future__ import annotations

from pathlib import Path

import pytest

from keeper.executive.authority_gateway import AuthorityProviderBinding
from keeper.executive.authority_gateway import AuthorityBackedSpecialistGateway
from keeper.executive.models import ExecutiveTask, ProjectCharter, SpecialistProfile
from keeper.executive.planning import WorkflowPlanner
from keeper.executive.runtime import ExecutiveRuntime
from tests.keeper.executive.authority_semantics import (
    ALL_CAPABILITIES,
    SemanticAuthorityTransport,
    semantic_gateway,
)
from tests.keeper.executive.test_intake_charters import approved_project


def _task_and_gateway(
    tmp_path: Path,
) -> tuple[
    ProjectCharter,
    ExecutiveTask,
    AuthorityBackedSpecialistGateway,
    SemanticAuthorityTransport,
    tuple[SpecialistProfile, ...],
]:
    service, project, charter = approved_project(tmp_path)
    _, tasks = WorkflowPlanner(service.repository).generate(project, charter)
    gateway, authority = semantic_gateway(tmp_path)
    specialists = gateway.specialists(charter)
    return charter, tasks[0], gateway, authority, specialists


def test_caller_created_profile_cannot_establish_qualification(
    tmp_path: Path,
) -> None:
    charter, task, gateway, _, _ = _task_and_gateway(tmp_path)
    forged = SpecialistProfile(
        "codex",
        "caller-model",
        "caller-session",
        task.required_capabilities,
        ("software",),
        True,
        True,
        "caller-independence",
        0,
        ("high",),
        True,
        1.0,
    )
    with pytest.raises(PermissionError, match="Authority state"):
        gateway.prepare(task, charter, forged)


def test_no_authority_reservation_means_no_provider_launch(
    tmp_path: Path,
) -> None:
    charter, task, gateway, authority, specialists = _task_and_gateway(
        tmp_path
    )
    plan = gateway.prepare(task, charter, specialists[0])
    with pytest.raises((PermissionError, KeyError)):
        gateway.execute(plan)
    assert authority.side_effect_count == 0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("task_id", "wrong-task", "binding"),
        ("registration_id", "wrong-provider", "binding"),
        ("provider_instance_id", "wrong-session", "binding"),
        ("provider_evidence_digest", "not-a-sha256", "SHA-256"),
    ],
)
def test_wrong_authenticated_completion_binding_is_rejected(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    charter, task, gateway, authority, specialists = _task_and_gateway(
        tmp_path
    )
    plan = gateway.prepare(task, charter, specialists[0])
    gateway.reserve(plan)
    authority.wrong_completion_field = (field, value)
    with pytest.raises(PermissionError, match=message):
        gateway.execute(plan)


def test_unsigned_completion_is_rejected(tmp_path: Path) -> None:
    charter, task, gateway, authority, specialists = _task_and_gateway(
        tmp_path
    )
    plan = gateway.prepare(task, charter, specialists[0])
    gateway.reserve(plan)
    authority.unsigned_completion = True
    with pytest.raises(PermissionError, match="authentication"):
        gateway.execute(plan)


def test_changed_executable_registration_is_rejected_before_launch(
    tmp_path: Path,
) -> None:
    charter, task, gateway, authority, specialists = _task_and_gateway(
        tmp_path
    )
    plan = gateway.prepare(task, charter, specialists[0])
    gateway.reserve(plan)
    authority.registrations[plan.registration_id][
        "canonical_executable_path"
    ] = "C:/Authority/substituted.exe"
    with pytest.raises(PermissionError, match="registration changed"):
        gateway.execute(plan)
    assert authority.side_effect_count == 0


def test_missing_distinct_reviewer_blocks_completion(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    only_author = (
        AuthorityProviderBinding(
            "registration-codex",
            "qualification-codex",
            ALL_CAPABILITIES,
            ("software", "general"),
            "codex-only",
        ),
    )
    gateway, authority = semantic_gateway(
        tmp_path, bindings=only_author
    )
    runtime = ExecutiveRuntime(service.repository, gateway)
    runtime.progress(project.project_id)
    runtime.progress(project.project_id)
    blocked = runtime.progress(project.project_id)
    architecture = next(
        task
        for task in service.repository.tasks(project.project_id)
        if task.title == "Architecture"
    )
    assert blocked.state == "BLOCKED"
    assert architecture.status == "REVIEW_REQUIRED"
    assert architecture.review_attempt_id is None
    assert len(authority.execution_calls) == 2


def test_review_plan_must_bind_current_artifact_revision(
    tmp_path: Path,
) -> None:
    service, project, _ = approved_project(tmp_path)
    gateway, _ = semantic_gateway(tmp_path)
    runtime = ExecutiveRuntime(service.repository, gateway)
    for _ in range(5):
        runtime.progress(project.project_id)
        current = next(
            task
            for task in service.repository.tasks(project.project_id)
            if task.title == "Architecture"
        )
        if current.review_attempt_id is not None:
            break
    architecture = next(
        task
        for task in service.repository.tasks(project.project_id)
        if task.title == "Architecture"
    )
    # A completed review remains durably bound to the author artifact digest.
    assert architecture.review_attempt_id is not None
    review = service.repository.review(architecture.review_attempt_id)
    assert (
        review["artifact_revision_digest"]
        == architecture.artifact_digest
    )
    with pytest.raises(PermissionError):
        service.repository.claim_review(
            architecture.task_id,
            expected_revision=architecture.revision,
            plan={
                **review["plan"],
                "authority_attempt_id": "copied-review-attempt",
                "artifact_revision_digest": "stale-artifact",
            },
        )
