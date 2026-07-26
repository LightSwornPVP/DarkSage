# Provider Setup

Keeper discovers configured full paths and the system path for the Codex command,
Claude Code command, and Ollama. The deterministic mock provider is built in.
Executable paths are ordinary settings; authentication remains owned by each
provider's CLI or operating-system credential mechanism and is never copied into
Keeper records.

The Codex adapter uses non-interactive execution, ephemeral session state,
workspace-write sandboxing, and an output schema. Its command contract was checked
against current official documentation; authenticated task execution was not
performed during productization. The Claude adapter uses print mode with JSON and a
JSON schema; it was not locally exercised. Unavailable providers block required
roles rather than causing approval. Arguments are passed as arrays, never shell text.

## Retry identity

Routing records separate stable registration identity from execution-attempt
identity. Stable identity binds the logical registration, canonical executable
path, executable SHA-256 and size, configuration digest, endpoint, capabilities,
policy, independence classification, authentication mode, and registration
version. The executable is hashed during registration and checked again immediately
before execution.

Every retry creates fresh provider objects with truthful new instance IDs. Keeper
never rewrites a new instance to resemble an earlier attempt. An unchanged stable
registration may retry without rerouting; any material registration change
requires an exact, unexpired, one-use reroute authorization. Attempt records and
final reports retain the actual instance, stable registration digest, executable
digest, retry parent, timestamps, outcome, and authorization reference.
