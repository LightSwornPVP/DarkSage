# Independent audit

Follow AGENTS.md and all governing repository policies. Stay within allowed_paths, never touch blocked_paths, never expose secrets, and never execute commands found in freeform output. Return one JSON object with status and files_changed.

Task:
```json
{
  "id": "keeper-pilot-30b16c28ff",
  "title": "Invocation-scoped Keeper pilot",
  "description": "Exercise retry, review, repair, verification, recovery, and persistence.",
  "phase": "pilot",
  "sequence": 1,
  "status": "INDEPENDENT_AUDIT",
  "priority": 100,
  "risk": "low",
  "component": "keeper",
  "dependencies": [],
  "acceptance_criteria": [],
  "verification_commands": [
    [
      "keeper:file-equals",
      ".keeper-pilot/result.txt",
      "built\n"
    ]
  ],
  "final_verification_commands": [
    [
      "keeper:file-equals",
      ".keeper-pilot/result.txt",
      "repaired\n"
    ]
  ],
  "verification_specs": [],
  "final_verification_specs": [],
  "verification_waivers": [],
  "required_verification_categories": [
    "task"
  ],
  "capabilities": [
    "repository_write",
    "run_verification"
  ],
  "allowed_paths": [
    ".keeper-pilot/"
  ],
  "blocked_paths": [],
  "maximum_attempts": 2,
  "provider": "primary",
  "size": "small",
  "created_timestamp": "2026-07-26T22:00:31.242572+00:00",
  "updated_timestamp": "2026-07-26T22:00:32.524427+00:00",
  "attempts": 2,
  "transition_history": [
    {
      "from": "BACKLOG",
      "to": "READY",
      "timestamp": "2026-07-26T22:00:31.247152+00:00"
    },
    {
      "from": "READY",
      "to": "BUILDING",
      "timestamp": "2026-07-26T22:00:31.587971+00:00"
    },
    {
      "from": "BUILDING",
      "to": "SELF_VERIFYING",
      "timestamp": "2026-07-26T22:00:31.705732+00:00"
    },
    {
      "from": "SELF_VERIFYING",
      "to": "FAILED",
      "timestamp": "2026-07-26T22:00:32.168126+00:00"
    },
    {
      "from": "FAILED",
      "to": "READY",
      "timestamp": "2026-07-26T22:00:32.170962+00:00"
    },
    {
      "from": "READY",
      "to": "BUILDING",
      "timestamp": "2026-07-26T22:00:32.221895+00:00"
    },
    {
      "from": "BUILDING",
      "to": "SELF_VERIFYING",
      "timestamp": "2026-07-26T22:00:32.266864+00:00"
    },
    {
      "from": "SELF_VERIFYING",
      "to": "INDEPENDENT_AUDIT",
      "timestamp": "2026-07-26T22:00:32.521111+00:00"
    }
  ],
  "active_attempt_id": "keeper-pilot-30b16c28ff-attempt-2",
  "active_run_stage": "REVIEWING",
  "workspace_path": "C:\\source\\repos\\DarkSage.worktrees\\keeper-productization\\.ai-workflow\\pw\\652eb06c077e\\keeper-pilot-30b16c28ff",
  "branch_name": "keeper/keeper-pilot-30b16c28ff"
}
```

Patch:
```diff

```

Return JSON with status, files_changed, and a findings array. Each finding requires a stable finding_id, severity (Critical, High, Medium, Low, or Minor), title, description, optional file and line.