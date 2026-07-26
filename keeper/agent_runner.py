from __future__ import annotations

import json
import uuid
import re
from pathlib import Path
from typing import Any, Callable

from keeper.models.run import RunRecord
from keeper.models.task import Task, now_iso
from keeper.providers.base import AgentProvider, AgentRequest
from keeper.provider_output import validate_provider_output
from keeper.recovery import atomic_write_json
from keeper.app.path_safety import validate_path_budget


class AgentRunner:
    def __init__(
        self,
        provider: AgentProvider,
        runs_directory: Path,
        timeout_seconds: int,
        maximum_output_bytes: int = 1_048_576,
        keeper_run_id: str | None = None,
        ownership_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.provider = provider
        self.runs_directory = runs_directory
        self.timeout_seconds = timeout_seconds
        self.maximum_output_bytes = maximum_output_bytes
        self.keeper_run_id = keeper_run_id
        self.ownership_sink = ownership_sink

    def run(
        self,
        task: Task,
        role: str,
        workspace: Path,
        branch: str,
        prompt: str,
        retry: int = 0,
        reasoning_level: str = "medium",
    ) -> RunRecord:
        role_label = {
            "builder": "b",
            "reviewer": "v",
            "repairer": "r",
            "post_repair_reviewer": "p",
        }.get(role, "x")
        run_id = f"pr-{role_label}-{uuid.uuid4().hex[:8]}"
        directory = self.runs_directory / run_id
        validate_path_budget(directory / "stderr.log", purpose="provider evidence path")
        directory.mkdir(parents=True, exist_ok=False)
        prompt_path = directory / "prompt.md"
        stdout_path = directory / "stdout.log"
        stderr_path = directory / "stderr.log"
        prompt_path.write_text(prompt, encoding="utf-8")
        record = RunRecord(
            run_id=run_id,
            task_id=task.id,
            role=role,
            provider_name=self.provider.provider_name,
            provider_instance_id=self.provider.instance_id,
            reasoning_level=reasoning_level,
            workspace_path=str(workspace),
            branch_name=branch,
            prompt_path=str(prompt_path),
            stdout_log_path=str(stdout_path),
            stderr_log_path=str(stderr_path),
            retry_count=retry,
        )
        record_path = directory / "run.json"
        atomic_write_json(record_path, record.to_dict())

        def process_started(process_id: int) -> None:
            record.process_id = process_id
            atomic_write_json(record_path, record.to_dict())

        def process_owned(ownership: dict[str, object]) -> None:
            record.process_ownership = {
                **ownership,
                "keeper_run_id": self.keeper_run_id,
                "task_id": task.id,
                "provider_run_id": run_id,
                "stage_id": task.active_run_stage,
                "provider_name": self.provider.provider_name,
                "provider_instance_id": self.provider.instance_id,
                "role": role,
                "evidence_path": str(directory.resolve()),
            }
            if self.ownership_sink is not None:
                self.ownership_sink(dict(record.process_ownership))
            atomic_write_json(record_path, record.to_dict())

        result = self.provider.run(
            AgentRequest(
                role,
                prompt_path,
                workspace,
                self.timeout_seconds,
                stdout_path,
                stderr_path,
                reasoning_level,
                process_started,
                process_owned,
            )
        )
        for log_path in (stdout_path, stderr_path):
            if log_path.exists():
                content = log_path.read_text(encoding="utf-8", errors="replace")
                redacted = re.sub(
                    r"(?i)(token|secret|password|passwd|api[_-]?key|credential)(\s*[:=]\s*)\S+",
                    r"\1\2[REDACTED]",
                    content,
                )
                log_path.write_text(redacted, encoding="utf-8")
        record.end_time = now_iso()
        record.process_exit_code = result.exit_code
        record.process_id = result.process_id
        record.status = "completed" if result.exit_code == 0 else "failed"
        if result.exit_code:
            record.failure_reason = "agent process timed out" if result.timed_out else "agent process failed"
        if stderr_path.exists() and stderr_path.stat().st_size > self.maximum_output_bytes:
            record.status = "failed"
            record.process_exit_code = 65
            record.failure_reason = "provider stderr exceeds configured size limit"
        if result.exit_code == 0:
            try:
                raw = (
                    json.dumps(result.output)
                    if result.output
                    else stdout_path.read_text(encoding="utf-8")
                )
                output = validate_provider_output(role, raw, self.maximum_output_bytes)
                changed = output["files_changed"]
                record.files_changed = [str(item) for item in changed]
            except (OSError, ValueError) as error:
                record.status = "failed"
                record.process_exit_code = 65
                record.failure_reason = f"invalid structured provider output: {error}"
        atomic_write_json(record_path, record.to_dict())
        return record
