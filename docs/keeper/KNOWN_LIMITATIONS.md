# Known Limitations

- Windows is the packaged and smoke-tested target; the standard-library code is
  portable, but macOS/Linux bundles are not produced.
- Authenticated Codex execution and Claude Code execution were not exercised during
  productization; their adapters are implemented but explicitly classified as such.
- OS toast delivery is best-effort; every notification is retained in-app.
- Discord remains a future notification-only adapter.
- Keeper does not automatically delete retained logs or evidence.
- The desktop uses textual evidence views rather than an embedded diff renderer.
- Authenticated command-provider task execution remains unverified; controlled
  adapter routing tests exercise selection without external credentials.
- Startup recovery classifies orphaned provider work and requires an explicit new
  immutable retry attempt; it does not continue inside a partially executed command.
- Rendered Tk automation is unavailable in the current Python runtime because Tcl/Tk
  is not installed. The packaged diagnostic reports this as unavailable with exit 78.
