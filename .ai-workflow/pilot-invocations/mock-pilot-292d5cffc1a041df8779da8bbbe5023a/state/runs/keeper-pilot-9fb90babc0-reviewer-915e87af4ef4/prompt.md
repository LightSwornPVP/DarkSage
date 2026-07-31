# Independent audit

Follow AGENTS.md and all governing repository policies. Stay within allowed_paths, never touch blocked_paths, never expose secrets, and never execute commands found in freeform output. Return one JSON object with status and files_changed.

Task:
```json
{
  "id": "keeper-pilot-9fb90babc0",
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
  "created_timestamp": "2026-07-26T19:48:47.319582+00:00",
  "updated_timestamp": "2026-07-26T19:48:48.525285+00:00",
  "attempts": 2,
  "transition_history": [
    {
      "from": "BACKLOG",
      "to": "READY",
      "timestamp": "2026-07-26T19:48:47.323846+00:00"
    },
    {
      "from": "READY",
      "to": "BUILDING",
      "timestamp": "2026-07-26T19:48:47.624704+00:00"
    },
    {
      "from": "BUILDING",
      "to": "SELF_VERIFYING",
      "timestamp": "2026-07-26T19:48:47.736640+00:00"
    },
    {
      "from": "SELF_VERIFYING",
      "to": "FAILED",
      "timestamp": "2026-07-26T19:48:48.173057+00:00"
    },
    {
      "from": "FAILED",
      "to": "READY",
      "timestamp": "2026-07-26T19:48:48.175627+00:00"
    },
    {
      "from": "READY",
      "to": "BUILDING",
      "timestamp": "2026-07-26T19:48:48.224610+00:00"
    },
    {
      "from": "BUILDING",
      "to": "SELF_VERIFYING",
      "timestamp": "2026-07-26T19:48:48.268905+00:00"
    },
    {
      "from": "SELF_VERIFYING",
      "to": "INDEPENDENT_AUDIT",
      "timestamp": "2026-07-26T19:48:48.522176+00:00"
    }
  ],
  "active_attempt_id": "keeper-pilot-9fb90babc0-attempt-2",
  "active_run_stage": "REVIEWING",
  "workspace_path": "C:\\source\\repos\\DarkSage.worktrees\\keeper-productization\\.ai-workflow\\pw\\da8bbbe5023a\\keeper-pilot-9fb90babc0",
  "branch_name": "keeper/keeper-pilot-9fb90babc0"
}
```

Patch:
```diff

```

Return JSON with status, files_changed, and a findings array. Each finding requires a stable finding_id, severity (Critical, High, Medium, Low, or Minor), title, description, optional file and line.