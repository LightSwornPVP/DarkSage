from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from keeper.provider_host.environment import (
    EnvironmentSnapshot,
    assert_attestation_matches,
    build_sanitized_environment,
)
from keeper.provider_host.identity import UserBinding, require_same_binding
from keeper.provider_host.protocol import (
    COMPLETION_PURPOSE,
    LAUNCH_PURPOSE,
    SETUP_PURPOSE,
    SETUP_RESULT_PURPOSE,
    EnvelopeSigner,
    EnvelopeVerifier,
    structured_digest,
    validate_launch_envelope,
    validate_setup_envelope,
)
from keeper.provider_host.replay_store import ProviderHostStore


class HostState(StrEnum):
    STARTING = "STARTING"
    READY = "READY"
    PREPARING = "PREPARING"
    CLAIMED = "CLAIMED"
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    LOCKED = "LOCKED"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"
    STALE = "STALE"


class Launcher(Protocol):
    def launch(
        self,
        envelope: Mapping[str, Any],
        environment: Mapping[str, str],
        cancel_requested: threading.Event,
        *,
        on_started: Callable[[dict[str, object]], None],
        on_resumed: Callable[[dict[str, object]], None],
    ) -> dict[str, Any]: ...


class SetupRunner(Protocol):
    def run_setup(
        self,
        envelope: Mapping[str, Any],
        environment: Mapping[str, str],
        cancel_requested: threading.Event,
        *,
        on_started: Callable[[dict[str, object]], None],
        on_resumed: Callable[[dict[str, object]], None],
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class HostIdentity:
    host_id: str
    authority_id: str
    binding: UserBinding


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    provider_id: str
    account_id: str
    session_id: str
    registration_id: str
    qualification_id: str
    executable_path: str
    executable_sha256: str
    executable_size: int
    file_identity: Mapping[str, int]
    authenticode_binding: Mapping[str, object]
    publisher: str
    version: str
    models: tuple[str, ...]
    efforts: tuple[str, ...]


class KeeperProviderHost:
    """Unelevated execution deputy for exact Authority-signed launches."""

    def __init__(
        self,
        *,
        identity: HostIdentity,
        observed_binding: Callable[[], UserBinding],
        authority_verifier: EnvelopeVerifier,
        host_signer: EnvelopeSigner,
        store: ProviderHostStore,
        provider_binding: ProviderBinding,
        environment_attestation_key: bytes,
        now: Callable[[], datetime] | None = None,
        maximum_ttl: timedelta = timedelta(minutes=2),
        maximum_future_skew: timedelta = timedelta(seconds=5),
    ) -> None:
        if not environment_attestation_key:
            raise ValueError("Provider Host environment attestation key is required")
        self.identity = identity
        self._observed_binding = observed_binding
        self._authority_verifier = authority_verifier
        self._host_signer = host_signer
        self._store = store
        self._provider_binding = provider_binding
        self._environment_attestation_key = environment_attestation_key
        self._now = now or (lambda: datetime.now(UTC))
        self._maximum_ttl = maximum_ttl
        self._maximum_future_skew = maximum_future_skew
        self._snapshots: dict[str, EnvironmentSnapshot] = {}
        self._active_cancel: threading.Event | None = None
        self._active_identity: tuple[str, str] | None = None
        self._lock = threading.RLock()
        self.state = HostState.STARTING

    def start(self) -> int:
        with self._lock:
            if self.state not in {HostState.STARTING, HostState.STOPPED}:
                raise PermissionError("Provider Host is already started")
            require_same_binding(self.identity.binding, self._observed_binding())
            recovered = self._store.recover_uncertain(
                "Provider Host restart with unresolved external effect"
            )
            self._set_state(HostState.READY)
            return recovered

    def prepare_environment(
        self, *, preparation_nonce: str, provider_bin: Path
    ) -> dict[str, Any]:
        with self._lock:
            self._require_ready()
            self._set_state(HostState.PREPARING)
            try:
                expected_bin = Path(
                    self._provider_binding.executable_path
                ).resolve(strict=True).parent
                if provider_bin.resolve(strict=True) != expected_bin:
                    raise PermissionError(
                        "Provider Host environment bin differs from registration"
                    )
                snapshot = build_sanitized_environment(
                    os.environ,
                    profile_path=Path(self.identity.binding.profile_path),
                    provider_bin=provider_bin,
                    preparation_nonce=preparation_nonce,
                    attestation_key=self._environment_attestation_key,
                )
                self._snapshots[preparation_nonce] = snapshot
                return self._host_signer.sign(
                    "keeper-provider-host-environment",
                    {
                        "host_id": self.identity.host_id,
                        "recorded_at": self._now().astimezone(UTC).isoformat(),
                        **snapshot.public_attestation(),
                    },
                )
            finally:
                if self.state is HostState.PREPARING:
                    self._set_state(HostState.READY)

    def execute(
        self,
        signed_envelope: Mapping[str, Any],
        launcher: Launcher,
        *,
        started_observer: Callable[[dict[str, object]], None] | None = None,
        resumed_observer: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._require_ready()
            require_same_binding(self.identity.binding, self._observed_binding())
            payload = self._authority_verifier.verify(
                signed_envelope, purpose=LAUNCH_PURPOSE
            )
            envelope = validate_launch_envelope(payload)
            self._validate_binding(envelope)
            nonce = str(envelope["environment"]["preparation_nonce"])
            snapshot = self._snapshots.pop(nonce, None)
            if snapshot is None:
                raise PermissionError("Provider Host environment preparation is absent")
            assert_attestation_matches(snapshot, envelope["environment"])
            for name in (
                "OPENAI_API_KEY",
                "CODEX_API_KEY",
                "CODEX_ACCESS_TOKEN",
            ):
                if name in snapshot.values:
                    raise PermissionError("Provider Host API-key environment is prohibited")
            envelope_digest = structured_digest(envelope)
            self._store.claim_launch(
                authority_id=str(envelope["authority_id"]),
                nonce=str(envelope["nonce"]),
                sequence=int(envelope["sequence"]),
                issued_at=str(envelope["issued_at"]),
                expires_at=str(envelope["expires_at"]),
                now=self._now(),
                maximum_ttl=self._maximum_ttl,
                maximum_future_skew=self._maximum_future_skew,
                launch_id=str(envelope["launch_id"]),
                authority_attempt_id=str(envelope["authority_attempt_id"]),
                envelope_digest=envelope_digest,
                workspace_path=str(envelope["workspace"]["canonical_path"]),
            )
            self._active_cancel = threading.Event()
            self._active_identity = (
                str(envelope["authority_attempt_id"]),
                str(envelope["launch_id"]),
            )
            self._set_state(HostState.CLAIMED)
        launch_id = str(envelope["launch_id"])
        started = False
        resumed = False

        def on_started(observation: dict[str, object]) -> None:
            nonlocal started
            self._store.transition(launch_id, "CLAIMED", "STARTED")
            started = True
            with self._lock:
                if self.state is HostState.CLAIMED:
                    self._set_state(HostState.STARTED)
            if started_observer is not None:
                started_observer(observation)

        def on_resumed(observation: dict[str, object]) -> None:
            nonlocal resumed
            self._store.transition(launch_id, "STARTED", "RUNNING")
            resumed = True
            with self._lock:
                if self.state is HostState.STARTED:
                    self._set_state(HostState.RUNNING)
            if resumed_observer is not None:
                resumed_observer(observation)

        try:
            cancellation = self._active_cancel
            if cancellation is None:
                raise RuntimeError("Provider Host cancellation state is unavailable")
            result = launcher.launch(
                envelope,
                snapshot.values,
                cancellation,
                on_started=on_started,
                on_resumed=on_resumed,
            )
            terminal = (
                "CANCELLED"
                if cancellation.is_set()
                else "COMPLETED"
                if result.get("exit_code") == 0
                else "FAILED"
            )
            expected = "RUNNING" if resumed else "STARTED" if started else "CLAIMED"
            self._store.transition(launch_id, expected, terminal)
            completion = {
                "authority_attempt_id": envelope["authority_attempt_id"],
                "envelope_digest": envelope_digest,
                "environment_digest": snapshot.digest,
                "evidence_digest": structured_digest(result),
                "host_id": self.identity.host_id,
                "launch_id": launch_id,
                "provider_input_digest": envelope["provider_input_digest"],
                "provider_output": result,
                "recorded_at": self._now().astimezone(UTC).isoformat(),
                "state": terminal,
            }
            return self._host_signer.sign(COMPLETION_PURPOSE, completion)
        except BaseException as error:
            current = self._store.get_launch(launch_id)["state"]
            if current in {"STARTED", "RUNNING"}:
                self._store.transition(
                    launch_id,
                    str(current),
                    "UNCERTAIN",
                    detail=type(error).__name__,
                )
            elif current == "CLAIMED":
                self._store.transition(
                    launch_id,
                    "CLAIMED",
                    "FAILED",
                    detail=type(error).__name__,
                )
            raise
        finally:
            with self._lock:
                self._active_cancel = None
                self._active_identity = None
                if self.state not in {
                    HostState.LOCKED,
                    HostState.DRAINING,
                    HostState.STOPPED,
                    HostState.STALE,
                }:
                    self._set_state(HostState.READY)

    def execute_setup(
        self,
        signed_envelope: Mapping[str, Any],
        runner: SetupRunner,
        *,
        started_observer: Callable[[dict[str, object]], None] | None = None,
        resumed_observer: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Execute an Authority-owned registration probe or qualification."""
        with self._lock:
            self._require_ready()
            require_same_binding(self.identity.binding, self._observed_binding())
            payload = self._authority_verifier.verify(
                signed_envelope, purpose=SETUP_PURPOSE
            )
            envelope = validate_setup_envelope(payload)
            self._validate_setup_binding(envelope)
            preparation_nonce = str(
                envelope["environment"]["preparation_nonce"]
            )
            snapshot = self._snapshots.pop(preparation_nonce, None)
            if snapshot is None:
                raise PermissionError(
                    "Provider Host setup environment preparation is absent"
                )
            assert_attestation_matches(snapshot, envelope["environment"])
            for name in (
                "OPENAI_API_KEY",
                "CODEX_API_KEY",
                "CODEX_ACCESS_TOKEN",
            ):
                if name in snapshot.values:
                    raise PermissionError(
                        "Provider Host setup API-key environment is prohibited"
                    )
            setup_id = str(envelope["setup_id"])
            envelope_digest = structured_digest(envelope)
            self._store.claim_launch(
                authority_id=str(envelope["authority_id"]),
                nonce=str(envelope["nonce"]),
                sequence=int(envelope["sequence"]),
                issued_at=str(envelope["issued_at"]),
                expires_at=str(envelope["expires_at"]),
                now=self._now(),
                maximum_ttl=self._maximum_ttl,
                maximum_future_skew=self._maximum_future_skew,
                launch_id=setup_id,
                authority_attempt_id=setup_id,
                envelope_digest=envelope_digest,
                workspace_path=str(envelope["workspace"]["canonical_path"]),
            )
            self._active_cancel = threading.Event()
            self._active_identity = (setup_id, setup_id)
            self._set_state(HostState.CLAIMED)
        started = False
        resumed = False

        def on_started(observation: dict[str, object]) -> None:
            nonlocal started
            self._store.transition(setup_id, "CLAIMED", "STARTED")
            started = True
            with self._lock:
                if self.state is HostState.CLAIMED:
                    self._set_state(HostState.STARTED)
            if started_observer is not None:
                started_observer(observation)

        def on_resumed(observation: dict[str, object]) -> None:
            nonlocal resumed
            self._store.transition(setup_id, "STARTED", "RUNNING")
            resumed = True
            with self._lock:
                if self.state is HostState.STARTED:
                    self._set_state(HostState.RUNNING)
            if resumed_observer is not None:
                resumed_observer(observation)

        try:
            cancellation = self._active_cancel
            if cancellation is None:
                raise RuntimeError(
                    "Provider Host setup cancellation state is unavailable"
                )
            observation = runner.run_setup(
                envelope,
                snapshot.values,
                cancellation,
                on_started=on_started,
                on_resumed=on_resumed,
            )
            expected = "RUNNING" if resumed else "STARTED" if started else "CLAIMED"
            terminal = (
                "CANCELLED"
                if cancellation.is_set()
                else "COMPLETED"
                if observation.get("exit_status") == 0
                else "FAILED"
            )
            self._store.transition(setup_id, expected, terminal)
            return self._host_signer.sign(
                SETUP_RESULT_PURPOSE,
                {
                    "authority_id": envelope["authority_id"],
                    "challenge": envelope["challenge"],
                    "environment_digest": snapshot.digest,
                    "host_id": self.identity.host_id,
                    "observation": observation,
                    "operation": envelope["operation"],
                    "provider_registration_id": envelope[
                        "provider_registration_id"
                    ],
                    "recorded_at": self._now().astimezone(UTC).isoformat(),
                    "setup_envelope_digest": envelope_digest,
                    "setup_id": setup_id,
                },
            )
        except BaseException as error:
            current = str(self._store.get_launch(setup_id)["state"])
            if current in {"STARTED", "RUNNING"}:
                self._store.transition(
                    setup_id, current, "UNCERTAIN", detail=type(error).__name__
                )
            elif current == "CLAIMED":
                self._store.transition(
                    setup_id, "CLAIMED", "FAILED", detail=type(error).__name__
                )
            raise
        finally:
            with self._lock:
                self._active_cancel = None
                self._active_identity = None
                if self.state not in {
                    HostState.LOCKED,
                    HostState.DRAINING,
                    HostState.STOPPED,
                    HostState.STALE,
                }:
                    self._set_state(HostState.READY)

    def lock_workstation(self) -> None:
        with self._lock:
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._set_state(HostState.LOCKED)

    def cancel_active(
        self, authority_attempt_id: str, launch_id: str
    ) -> bool:
        with self._lock:
            if (
                self._active_cancel is None
                or self._active_identity
                != (authority_attempt_id, launch_id)
            ):
                return False
            self._active_cancel.set()
            return True

    def unlock_workstation(self) -> None:
        with self._lock:
            if self.state is not HostState.LOCKED or self._active_cancel is not None:
                raise PermissionError("Provider Host cannot unlock while work is active")
            require_same_binding(self.identity.binding, self._observed_binding())
            self._set_state(HostState.READY)

    def drain(self) -> None:
        with self._lock:
            self._set_state(HostState.DRAINING)

    def logoff(self) -> None:
        with self._lock:
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._snapshots.clear()
            self._set_state(HostState.STOPPED)

    def mark_stale(self, detail: str = "Authority connection is stale") -> None:
        with self._lock:
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._set_state(HostState.STALE, detail)

    def status(self) -> dict[str, object]:
        return {
            "authority_id": self.identity.authority_id,
            "host_id": self.identity.host_id,
            "host_protocol": "keeper-provider-host/1",
            "pending_environment_preparations": len(self._snapshots),
            "state": self.state.value,
            "user_binding": self.identity.binding.as_dict(),
            "provider_binding": {
                "account_id": self._provider_binding.account_id,
                "authenticode_binding": dict(
                    self._provider_binding.authenticode_binding
                ),
                "efforts": list(self._provider_binding.efforts),
                "executable_path": self._provider_binding.executable_path,
                "executable_sha256": self._provider_binding.executable_sha256,
                "executable_size": self._provider_binding.executable_size,
                "file_identity": dict(self._provider_binding.file_identity),
                "models": list(self._provider_binding.models),
                "provider_id": self._provider_binding.provider_id,
                "publisher": self._provider_binding.publisher,
                "registration_id": self._provider_binding.registration_id,
                "qualification_id": self._provider_binding.qualification_id,
                "session_id": self._provider_binding.session_id,
                "version": self._provider_binding.version,
            },
        }

    @property
    def provider_bin(self) -> Path:
        return Path(self._provider_binding.executable_path).resolve(
            strict=True
        ).parent

    def _validate_binding(self, envelope: Mapping[str, Any]) -> None:
        provider = self._provider_binding
        if (
            envelope["authority_id"] != self.identity.authority_id
            or envelope["host_id"] != self.identity.host_id
            or envelope["user_binding"] != self.identity.binding.as_dict()
            or envelope["provider_id"] != provider.provider_id
            or envelope["account_id"] != provider.account_id
            or envelope["provider_session_id"] != provider.session_id
            or envelope["provider_registration_id"] != provider.registration_id
            or envelope["provider_qualification_id"] != provider.qualification_id
            or envelope["executable"]["sha256"] != provider.executable_sha256
            or envelope["executable"]["size"] != provider.executable_size
            or envelope["executable"]["file_identity"] != dict(provider.file_identity)
            or envelope["executable"]["authenticode_binding"]
            != dict(provider.authenticode_binding)
            or envelope["executable"]["publisher"] != provider.publisher
            or envelope["executable"]["version"] != provider.version
            or envelope["model_id"] not in provider.models
            or envelope["effort"] not in provider.efforts
        ):
            raise PermissionError("Provider Host qualified binding differs")
        executable = Path(str(envelope["executable"]["path"]))
        expected = Path(provider.executable_path).resolve(strict=True)
        if (
            not executable.is_absolute()
            or os.path.normcase(os.path.abspath(str(executable)))
            != os.path.normcase(str(expected))
            or hashlib.sha256(expected.read_bytes()).hexdigest()
            != provider.executable_sha256
        ):
            raise PermissionError("Provider Host executable path or hash differs")

    def _validate_setup_binding(self, envelope: Mapping[str, Any]) -> None:
        provider = self._provider_binding
        registration_matches = (
            envelope["operation"] == "REGISTER_PROBE"
            or envelope["provider_registration_id"] == provider.registration_id
        )
        if (
            envelope["authority_id"] != self.identity.authority_id
            or envelope["host_id"] != self.identity.host_id
            or envelope["user_binding"] != self.identity.binding.as_dict()
            or envelope["provider_id"] != provider.provider_id
            or not registration_matches
            or envelope["executable"]["sha256"] != provider.executable_sha256
            or envelope["executable"]["size"] != provider.executable_size
            or envelope["executable"]["file_identity"]
            != dict(provider.file_identity)
            or envelope["executable"]["authenticode_binding"]
            != dict(provider.authenticode_binding)
            or envelope["executable"]["publisher"] != provider.publisher
            or envelope["executable"]["version"] != provider.version
            or envelope["model_id"] not in provider.models
            or (
                envelope["operation"] != "REGISTER_PROBE"
                and envelope["account_binding"].get(
                    "account_identity_digest"
                )
                != provider.account_id.removeprefix(
                    "chatgpt-subscription:"
                )
            )
        ):
            raise PermissionError("Provider Host setup binding differs")
        executable = Path(str(envelope["executable"]["path"]))
        expected = Path(provider.executable_path).resolve(strict=True)
        if (
            not executable.is_absolute()
            or os.path.normcase(os.path.abspath(str(executable)))
            != os.path.normcase(str(expected))
            or hashlib.sha256(expected.read_bytes()).hexdigest()
            != provider.executable_sha256
        ):
            raise PermissionError(
                "Provider Host setup executable path or hash differs"
            )
        workspace = Path(str(envelope["workspace"]["canonical_path"]))
        setup_root = (
            Path(self.identity.binding.profile_path)
            / "AppData"
            / "Local"
            / "Keeper"
            / "ProviderHost"
            / "setup"
        )
        setup_root.mkdir(parents=True, exist_ok=True)
        canonical_root = setup_root.resolve(strict=True)
        expected_workspace = canonical_root / hashlib.sha256(
            str(envelope["setup_id"]).encode("utf-8")
        ).hexdigest()
        if (
            not workspace.is_absolute()
            or os.path.normcase(os.path.abspath(str(workspace)))
            != os.path.normcase(str(expected_workspace))
        ):
            raise PermissionError("Provider Host setup workspace differs")
        try:
            workspace.mkdir(exist_ok=False)
        except FileExistsError as error:
            raise PermissionError(
                "Provider Host setup workspace is replayed"
            ) from error
        if workspace.resolve(strict=True).parent != canonical_root:
            raise PermissionError("Provider Host setup workspace is unsafe")

    def _require_ready(self) -> None:
        if self.state is not HostState.READY:
            raise PermissionError(f"Provider Host state {self.state.value} rejects work")

    def _set_state(self, state: HostState, detail: str = "") -> None:
        self.state = state
        self._store.set_host_state(state.value, detail)
