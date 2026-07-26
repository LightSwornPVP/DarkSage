# Developer Architecture

`keeper.desktop` is a Tkinter presentation layer over `KeeperApplication`.
`keeper.app.storage` owns transactional versioned SQLite records. Lifecycle,
verification policy, Git safety, security, notifications, and reporting are
separate services. The approved orchestration engine and process-tree provider
runner remain authoritative for workflow execution.

Provider adapters implement the existing `AgentProvider` request/result boundary.
No local server or IPC is used. This keeps the attack surface and packaging
dependency set small while permitting a future presentation layer to reuse the
display-independent service.
