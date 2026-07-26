from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from keeper.agent_runner import AgentRunner
from keeper.config import KeeperConfig
from keeper.orchestrator import Keeper
from keeper.providers.codex_cli import CliProvider
from keeper.providers.mock import MockProvider
from keeper.providers.ollama import OllamaProvider
from keeper.providers.routing import ProviderRouter
from keeper.task_queue import TaskQueue
from keeper.verifier import VerificationCommand, Verifier
from keeper.workspace import WorkspaceManager


def build_keeper(root: Path, mock: bool = False) -> Keeper:
    config = KeeperConfig.load(root)
    provider = (
        MockProvider(output={"status": "completed", "files_changed": [], "findings": []})
        if mock
        else CliProvider(config.provider_command)
    )
    reviewer_provider = (
        MockProvider(output={"status": "completed", "files_changed": [], "findings": []})
        if mock
        else CliProvider(config.provider_command)
    )
    repairer_provider = (
        MockProvider(output={"status": "completed", "files_changed": [], "findings": []})
        if mock
        else CliProvider(config.provider_command)
    )
    post_repair_reviewer = (
        MockProvider(output={"status": "completed", "files_changed": [], "findings": [], "dispositions": []})
        if mock
        else CliProvider(config.provider_command)
    )
    ollama = (
        MockProvider(
            output={"status": "completed", "files_changed": [], "findings": []},
            provider_name=config.ollama_model,
        )
        if mock
        else OllamaProvider(config.ollama_model, config.ollama_endpoint)
    )
    router = ProviderRouter(
        {
            "primary_builder": provider,
            "primary_reviewer": reviewer_provider,
            "primary_repairer": repairer_provider,
            "primary_post_repair_reviewer": post_repair_reviewer,
            "ollama": ollama,
        },
        dict(config.provider_routes),
    )
    runner = AgentRunner(provider, config.state_root / "runs", config.process_timeout_seconds)
    return Keeper(
        config,
        runner,
        WorkspaceManager(
            config.repository_root,
            config.workspace_root,
            config.state_root / "workspace-ownership",
        ),
        router,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="python -m keeper", description="Run the local Keeper workflow.")
    result.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    result.add_argument("--mock", action="store_true", help="use the deterministic test provider")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("start", help="recover and process tasks until the queue is empty")
    commands.add_parser("run-next", help="run the next eligible task")
    commands.add_parser("resume", help="clear pause state, recover, and run the next task")
    commands.add_parser("pause", help="stop progression after the current process")
    commands.add_parser("status", help="show queue and pause state")
    commands.add_parser("list-tasks", help="list task IDs and statuses")
    show = commands.add_parser("show-task", help="print one task")
    show.add_argument("task_id")
    commands.add_parser("verify", help="run Keeper's self-verification")
    commands.add_parser("recover", help="record decisions for interrupted runs")
    cleanup = commands.add_parser("cleanup-worktrees", help="remove a clean task worktree")
    cleanup.add_argument("path", type=Path)
    return result


def main(arguments: list[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    root = options.root.resolve()
    keeper = build_keeper(root, options.mock)
    try:
        if options.command == "pause":
            keeper.pause()
            print("Keeper is paused.")
        elif options.command == "status":
            print(json.dumps(keeper.status(), indent=2))
        elif options.command == "list-tasks":
            for task in keeper.queue.load():
                print(f"{task.id}\t{task.status.value}\t{task.title}")
        elif options.command == "show-task":
            shown_task = next((item for item in keeper.queue.load() if item.id == options.task_id), None)
            if shown_task is None:
                raise LookupError(f"task not found: {options.task_id}")
            print(json.dumps(shown_task.to_dict(), indent=2))
        elif options.command == "verify":
            commands = [
                VerificationCommand([sys.executable, "-m", "mypy", "keeper"]),
                VerificationCommand([sys.executable, "-m", "pytest", "-q", "tests/keeper"]),
            ]
            results = Verifier().run(root, commands)
            for result in results:
                print(f"{'PASS' if result.passed else 'FAIL'}: {' '.join(result.arguments)}")
                if result.stdout:
                    print(result.stdout, end="")
                if result.stderr:
                    print(result.stderr, file=sys.stderr, end="")
            return 0 if Verifier.required_passed(results) else 1
        elif options.command == "recover":
            print(json.dumps(keeper.recover(), indent=2))
        elif options.command == "cleanup-worktrees":
            keeper.workspace_manager.cleanup(options.path.resolve())
        elif options.command == "resume":
            resumed_task = keeper.resume()
            print(resumed_task.id if resumed_task else "No eligible tasks.")
        elif options.command == "run-next":
            next_task = keeper.run_next()
            print(next_task.id if next_task else "No eligible tasks.")
        elif options.command == "start":
            keeper.recover()
            while started_task := keeper.run_next():
                print(f"{started_task.id}: {started_task.status.value}")
                if started_task.status.value in {"BLOCKED", "FAILED"}:
                    break
        return 0
    except (FileNotFoundError, LookupError, PermissionError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
