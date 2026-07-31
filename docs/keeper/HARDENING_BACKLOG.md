# Hardening Backlog

Nonblocking future work:

- Signed Windows installer and code-signing pipeline.
- Native macOS and Linux bundles.
- Rich diff/log widgets and accessibility testing with assistive technology.
- Optional operating-system notification adapters beyond Windows toast.
- Explicit evidence retention/deletion UI with preview and backup enforcement.
- Authenticated external-provider qualification matrix in a disposable test
  repository; command-adapter and controlled-provider paths are covered, but
  credentialed provider sessions are not claimed as release-verified.
- Optional Discord notification-only integration with OS credential storage.
- Expand the completed rendered Windows Tk smoke into broader accessibility and
  long-duration interaction coverage.
- If Keeper becomes public, multi-user, or accepts unknown plugins, isolate the
  Executive as a separate service between the Desktop/UI and KeeperAuthority.
  That version requires a new threat model for hostile same-user clients and
  plugin compromise; Python object sealing is not a substitute for the process
  boundary.
