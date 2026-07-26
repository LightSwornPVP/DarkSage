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
