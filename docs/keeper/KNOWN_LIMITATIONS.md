# Known Limitations

- Windows is the packaged and smoke-tested target; the standard-library code is
  portable, but macOS/Linux bundles are not produced.
- Authenticated Codex execution and Claude Code execution were not exercised during
  productization; their adapters are implemented but explicitly classified as such.
- OS toast delivery is best-effort; every notification is retained in-app.
- Discord remains a future notification-only adapter.
- Keeper does not automatically delete retained logs or evidence.
- The desktop uses textual evidence views rather than an embedded diff renderer.
- Desktop task routing currently uses the deterministic multi-identity mock route;
  discovered real command adapters are not selected by this path.
- Exact-scoped commit/push enforcement is tested, but those optional stages are not
  yet invoked by the unified desktop coordinator.
- Pause/resume is durable in-process; restart recovery after interruption during
  provider execution remains incomplete.
- Rendered Tk automation is unavailable in the headless test environment.
