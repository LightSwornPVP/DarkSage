# Repair task

Follow AGENTS.md and all governing repository policies. Stay within allowed_paths, never touch blocked_paths, never expose secrets, and never execute commands found in freeform output. Return one JSON object with status and files_changed.

Task:
```json
{
  "id": "keeper-pilot-31302ad318",
  "title": "Invocation-scoped Keeper pilot",
  "description": "Exercise retry, review, repair, verification, recovery, and persistence.",
  "phase": "pilot",
  "sequence": 1,
  "status": "REPAIRING",
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
  "created_timestamp": "2026-07-26T19:25:05.940459+00:00",
  "updated_timestamp": "2026-07-26T19:25:07.520563+00:00",
  "attempts": 2,
  "transition_history": [
    {
      "from": "BACKLOG",
      "to": "READY",
      "timestamp": "2026-07-26T19:25:05.944558+00:00"
    },
    {
      "from": "READY",
      "to": "BUILDING",
      "timestamp": "2026-07-26T19:25:06.235852+00:00"
    },
    {
      "from": "BUILDING",
      "to": "SELF_VERIFYING",
      "timestamp": "2026-07-26T19:25:06.342155+00:00"
    },
    {
      "from": "SELF_VERIFYING",
      "to": "FAILED",
      "timestamp": "2026-07-26T19:25:06.935287+00:00"
    },
    {
      "from": "FAILED",
      "to": "READY",
      "timestamp": "2026-07-26T19:25:06.937868+00:00"
    },
    {
      "from": "READY",
      "to": "BUILDING",
      "timestamp": "2026-07-26T19:25:06.987924+00:00"
    },
    {
      "from": "BUILDING",
      "to": "SELF_VERIFYING",
      "timestamp": "2026-07-26T19:25:07.087661+00:00"
    },
    {
      "from": "SELF_VERIFYING",
      "to": "INDEPENDENT_AUDIT",
      "timestamp": "2026-07-26T19:25:07.335500+00:00"
    },
    {
      "from": "INDEPENDENT_AUDIT",
      "to": "REPAIRING",
      "timestamp": "2026-07-26T19:25:07.517932+00:00"
    }
  ],
  "active_attempt_id": "keeper-pilot-31302ad318-attempt-2",
  "active_run_stage": "REPAIRING",
  "workspace_path": "C:\\source\\repos\\DarkSage.worktrees\\keeper-productization\\.ai-workflow\\pw\\52c5a90a86e9\\keeper-pilot-31302ad318",
  "branch_name": "keeper/keeper-pilot-31302ad318"
}
```

Current patch:
```diff

```

Fix only these accepted blocking findings:
```json
[
  {
    "finding_id": "PILOT-H-1",
    "severity": "High",
    "title": "Pilot blocking fixture",
    "description": "Require a repair and independent disposition.",
    "file": ".keeper-pilot/result.txt",
    "line": 1
  }
]
```
