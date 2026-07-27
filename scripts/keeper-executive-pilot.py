from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from keeper.executive.models import SpecialistProfile
from keeper.executive.runtime import ExecutiveRuntime
from keeper.executive.service import KeeperExecutive
from keeper.executive.specialists import SpecialistResult


class PilotGateway:
    def execute(
        self, specialist: SpecialistProfile, brief: object, guidance: object
    ) -> SpecialistResult:
        task_id = str(getattr(guidance, "task_id"))
        outputs = tuple(getattr(guidance, "required_outputs"))
        role = str(getattr(guidance, "role"))
        scope = tuple(getattr(guidance, "allowed_scope"))
        return SpecialistResult(
            task_id,
            specialist.provider_id,
            specialist.model_id,
            specialist.session_id,
            "COMPLETED",
            outputs,
            (f"pilot:{task_id}",),
            {},
            (str(scope[0]),),
            role,
            ("passed",),
        )


def pilot_profiles() -> tuple[SpecialistProfile, ...]:
    capabilities = (
        "requirements", "architecture", "implementation", "testing",
        "security", "packaging", "acceptance",
    )
    return tuple(
        SpecialistProfile(
            "mock",
            f"pilot-{identity}-{capability}",
            f"pilot-session-{identity}-{capability}",
            (capability,),
            ("software",),
            True,
            True,
            identity,
            0,
            ("medium",),
            True,
            1.0,
        )
        for capability in capabilities
        for identity in ("author", "reviewer")
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="keeper-executive-pilot-") as directory:
        root = Path(directory)
        executive = KeeperExecutive(root / "keeper.db")
        project, intake = executive.begin(
            f"I want a small application called Pilot List in {root}. "
            "Use full delegation and no spending."
        )
        draft = executive.draft(
            project.project_id,
            intake,
            founder_revisions={
                "success_criteria": ("all pilot checks pass",),
                "target_audience": "pilot user",
                "approved_providers": ("mock",),
                "approved_tools": ("filesystem",),
            },
        )
        approved, _ = executive.charters.approve(
            executive.charters.propose(draft),
            approver="Founder",
            source_interaction_id="local-pilot",
        )
        active = executive.charters.activate(approved)
        runtime = ExecutiveRuntime(
            executive.repository, PilotGateway(), pilot_profiles()
        )
        for _ in range(20):
            active = runtime.progress(active.project_id)
            if active.state == "COMPLETED":
                break
        print(
            json.dumps(
                {
                    "project_id": active.project_id,
                    "status": active.state,
                    "tasks": len(executive.repository.tasks(active.project_id)),
                    "evidence": len(executive.repository.memories(active.project_id)),
                },
                sort_keys=True,
            )
        )
        return 0 if active.state == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
