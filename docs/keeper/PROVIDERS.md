# Provider Setup

Keeper discovers configured full paths and the system path for the Codex command,
Claude Code command, and Ollama. The deterministic mock provider is built in.
Executable paths are ordinary settings; authentication remains owned by each
provider's CLI or operating-system credential mechanism and is never copied into
Keeper records.

A configured path is not authority. Before desktop diagnostics, routing, or the
standalone `start` and `run-next` commands can use a command provider, an
authorized registration must be created and stored. The schema-versioned record
binds component identities, canonical paths, hashes and sizes, exact invocation,
endpoint, authentication profile reference, capabilities, role eligibility,
policy, independence, qualification, authorization, revocation, and expiration.
Its canonical digest covers every field other than the digest itself. Missing,
extra, mistyped, expired, revoked, or mutated fields fail closed.

Registration does not execute the provider or manufacture a version. Discovery
reports `registered` until an explicitly protected qualification records its
version, timestamp, method, result, and qualifying component digests. Standalone
configuration uses this same schema and must bind its exact `provider_command`
array; legacy registration objects are rejected rather than implicitly upgraded.

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
version and qualification metadata. The canonical registration digest is checked
during discovery, and executable components are checked again immediately before
execution.

Every retry creates fresh provider objects with truthful new instance IDs. Keeper
never rewrites a new instance to resemble an earlier attempt. An unchanged stable
registration may retry without rerouting; any material registration change
requires an exact, unexpired, one-use reroute authorization. Attempt records and
final reports retain the actual instance, stable registration digest, executable
digest, retry parent, timestamps, outcome, and authorization reference.
