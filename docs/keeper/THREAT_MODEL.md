# Threat Model

Keeper treats provider output and repository content as untrusted data. Structured
commands, argument arrays, registered verification validators, scoped paths,
independent review, bounded output, redaction, and explicit authorization mitigate
command/prompt injection, fabricated completion, credential leakage, and replay.

Resolved paths must remain inside the repository; traversal, symlink escape, unsafe
archives, conflicts, and unexpected binaries fail closed. SQLite records and report
indexes carry hashes to expose corruption or evidence tampering. Provider processes
are bounded by timeout/cancellation and descendant cleanup.

Residual risks include compromise of the host account, provider executable, Python
runtime, Git executable, or OS credential store. Keeper is not a sandbox for hostile
native repositories and must not run with elevated privileges.
