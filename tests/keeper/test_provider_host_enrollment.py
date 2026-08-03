from __future__ import annotations

import base64
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import pytest

from keeper.authority_service.provider_host_enrollment import (
    ENROLLMENT_SYSTEM_CHARTER,
    ENROLLMENT_SYSTEM_PROJECT,
    ProviderHostEnrollmentCoordinator,
)
from keeper.authority_service.client import TestAuthorityServiceClient
from keeper.authority_service.core import AuthorityServiceCore
from keeper.authority_service.observer import ServiceProviderObserver
from keeper.authority_service.restricted_process import (
    WindowsSessionQueryResult,
    WindowsSessionQueryStatus,
)
from keeper.authority_service.windows_identity import (
    NamedPipeClientProcessBinding,
    NamedPipeClientProcessIdentity,
)
from keeper.authority_service.store import AuthorityStore
from keeper.executive.founder_capability import TestFounderCapabilityVerifier
from keeper.executive.founder_auth import TestFounderAuthenticator
from keeper.provider_host.bootstrap import ProviderHostBootstrap
from keeper.provider_host.cli import (
    _config,
    _revoked_status,
    _validate_authority_compatibility,
)
from keeper.provider_host.enrollment_client import ProviderHostEnrollmentClient
from keeper.provider_host.enrollment import (
    ENROLLMENT_PROOF_PURPOSE,
    stable_host_identity,
)
from keeper.provider_host.identity import UserBinding
from keeper.provider_host.install import ProviderHostInstaller
from keeper.provider_host.protocol import (
    HOST_PROTOCOL,
    TestEnvelopeIdentity as EnvelopeTestIdentity,
    structured_digest,
)
from tests.keeper.authority_testkit import make_test_founder_capability


AUTHORITY = EnvelopeTestIdentity("authority-test", b"authority-enrollment-key")
HOST = EnvelopeTestIdentity("host-test", b"host-enrollment-key")
SID = "S-1-5-21-1000-1000-1000-1001"


class _PublicTestSigner:
    def __init__(self, identity: EnvelopeTestIdentity) -> None:
        self._identity = identity
        self.identity = identity.identity
        self.key_id = identity.key_id
        self.production = False
        self.key_name = "KeeperProviderHost-test-key"

    def sign(self, purpose: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._identity.sign(purpose, payload)

    def public_configuration(self) -> dict[str, object]:
        return _public(self._identity)


class _AuthorityAdapter:
    def __init__(self, coordinator: ProviderHostEnrollmentCoordinator) -> None:
        self.coordinator = coordinator

    def provider_host_enrollment_status(self) -> dict[str, Any]:
        return self.coordinator.status()

    def begin_provider_host_enrollment(
        self, *, founder_capability: dict[str, object], proposal: dict[str, object]
    ) -> dict[str, Any]:
        return self.coordinator.begin(
            {"founder_capability": founder_capability, "proposal": proposal}, SID
        )

    def complete_provider_host_enrollment(
        self, enrollment_id: str, proof: dict[str, object]
    ) -> dict[str, Any]:
        return self.coordinator.complete(
            {"enrollment_id": enrollment_id, "proof": proof}, SID
        )

    def reconcile_provider_host_enrollment(
        self, enrollment_id: str, proof: dict[str, object] | None
    ) -> dict[str, Any]:
        return self.coordinator.reconcile(
            {"enrollment_id": enrollment_id, "proof": proof}, SID
        )

    def revoke_provider_host_enrollment(
        self, enrollment_id: str, founder_capability: dict[str, object]
    ) -> dict[str, Any]:
        return self.coordinator.revoke(
            {
                "enrollment_id": enrollment_id,
                "founder_capability": founder_capability,
            },
            SID,
        )


class _LostBeginAdapter(_AuthorityAdapter):
    def __init__(self, coordinator: ProviderHostEnrollmentCoordinator) -> None:
        super().__init__(coordinator)
        self.lost = False

    def begin_provider_host_enrollment(
        self, *, founder_capability: dict[str, object], proposal: dict[str, object]
    ) -> dict[str, Any]:
        result = super().begin_provider_host_enrollment(
            founder_capability=founder_capability, proposal=proposal
        )
        if not self.lost:
            self.lost = True
            raise OSError("simulated lost enrollment authorization response")
        return result


class _VerifierHolder:
    def verifier(self) -> EnvelopeTestIdentity:
        return AUTHORITY


class _FakeClientBinding(NamedPipeClientProcessBinding):
    def __init__(self) -> None:
        self.pipe = 9
        self.identity = NamedPipeClientProcessIdentity(77, 1, SID, "LOCALHOST")

    @property
    def profile_token(self) -> int:
        return 86

    def revalidate(self, expected_sid: str) -> NamedPipeClientProcessIdentity:
        if expected_sid.casefold() != SID.casefold():
            raise PermissionError("test SID differs")
        return self.identity

    def release(self) -> None:
        return


class _Observer:
    def __init__(self) -> None:
        self.activations: list[str] = []
        self.deactivations: list[str] = []

    def validate_provider_host_enrollment_proposal(
        self, proposal: Mapping[str, Any], client_sid: str
    ) -> dict[str, Any]:
        if client_sid != SID or proposal["user_binding"]["user_sid"] != SID:
            raise PermissionError("test enrollment user differs")
        return dict(proposal)

    def provider_host_runtime_configuration(
        self,
        proposal: Mapping[str, Any],
        *,
        enrollment_id: str,
        authority_id: str,
        authority_public_identity: Mapping[str, object],
    ) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "enrollment_id": enrollment_id,
            "authority_id": authority_id,
            "authority_peer": {
                "executable_file_identity": {
                    "device_id": 1,
                    "file_id": 2,
                    "modified_ns": 3,
                    "schema_version": 1,
                    "size": 4,
                },
                "executable_path": "C:/ProgramData/Keeper/python.exe",
                "executable_sha256": "a" * 64,
                "session_id": 0,
                "user_sid": "S-1-5-80-100",
            },
            "authority_public_identity": dict(authority_public_identity),
            "host_id": str(proposal["host_id"]),
            "host_key_name": "KeeperProviderHost-test-key",
            "host_public_identity": dict(proposal["host_public_identity"]),
            "output_root": str(proposal["output_root"]),
            "pipe_name": str(proposal["pipe_name"]),
            "state_root": str(proposal["state_root"]),
            "user_binding": dict(proposal["user_binding"]),
        }

    def activate(self, record: Mapping[str, Any]) -> None:
        self.activations.append(str(record["enrollment_id"]))

    def deactivate(self, record: Mapping[str, Any]) -> None:
        self.deactivations.append(str(record["enrollment_id"]))


class _FailOnceObserver(_Observer):
    def __init__(self) -> None:
        super().__init__()
        self.failed = False

    def activate(self, record: Mapping[str, Any]) -> None:
        if not self.failed:
            self.failed = True
            raise OSError("simulated activation interruption")
        super().activate(record)


class _CancelledAuthenticator(TestFounderAuthenticator):
    def authenticate(self, challenge: Any) -> Any:
        raise PermissionError("Windows Founder authentication was canceled")


def _public(identity: EnvelopeTestIdentity) -> dict[str, object]:
    return {
        "schema_version": 1,
        "algorithm": "RSA-PKCS1-SHA256",
        "identity": identity.identity,
        "key_id": identity.key_id,
        "modulus": base64.b64encode(b"test-modulus").decode("ascii"),
        "exponent": base64.b64encode(b"\x01\x00\x01").decode("ascii"),
    }


def _proposal(tmp_path: Path, *, generation: int = 1) -> dict[str, Any]:
    now = datetime.now(UTC)
    executable = tmp_path / "install" / "versions" / "1.7.1" / "KeeperProviderHost.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ-provider-host-test")
    stat = executable.stat()
    payload = {
        "schema_version": 1,
        "authority_protocol_version": 7,
        "authority_schema_version": 6,
        "enrollment_generation": generation,
        "expires_at": (now + timedelta(minutes=1)).isoformat(),
        "host_id": HOST.identity,
        "host_key_name": "KeeperProviderHost-test-key",
        "host_protocol": HOST_PROTOCOL,
        "host_public_identity": _public(HOST),
        "installation": {
            "authenticode_binding": {
                "certificate_thumbprint": None,
                "publisher_subject": None,
                "source": "windows-authenticode",
                "status": "NotSigned",
            },
            "executable_file_identity": {
                "device_id": stat.st_dev,
                "file_id": stat.st_ino,
                "modified_ns": stat.st_mtime_ns,
                "schema_version": 1,
                "size": stat.st_size,
            },
            "executable_path": str(executable.resolve()),
            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "executable_size": stat.st_size,
            "install_root": str((tmp_path / "install").resolve()),
            "manifest_sha256": "b" * 64,
            "package_version": "1.7.1",
        },
        "issued_at": now.isoformat(),
        "output_root": str((tmp_path / "install" / "state" / "output").resolve()),
        "pipe_name": r"\\.\pipe\KeeperProviderHost-test",
        "proposal_nonce": "proposal-nonce-test",
        "service_key_id": "keeper-authority:test",
        "state_root": str((tmp_path / "install" / "state").resolve()),
        "user_binding": {
            "profile_path": str((tmp_path / "profile").resolve()),
            "session_id": 1,
            "user_sid": SID,
        },
    }
    return HOST.sign("keeper-provider-host-enrollment-proposal", payload)


def _coordinator(tmp_path: Path, observer: _Observer) -> ProviderHostEnrollmentCoordinator:
    store = AuthorityStore(tmp_path / "authority" / "authority.db")
    store.migrate()
    return ProviderHostEnrollmentCoordinator(
        store=store,
        service_key_id="keeper-authority:test",
        authority_protocol_version=7,
        authority_schema_version=6,
        founder_verifier=TestFounderCapabilityVerifier(),
        authority_signer=AUTHORITY,
        authority_public_identity=_public(AUTHORITY),
        proposal_observer=observer,
        activate=observer.activate,
        deactivate=observer.deactivate,
        host_verifier_factory=lambda value: HOST,
    )


def _installed_bootstrap(tmp_path: Path) -> ProviderHostBootstrap:
    package = tmp_path / "package"
    package.mkdir()
    executable = package / "KeeperProviderHost.exe"
    library = package / "lib" / "runtime.dll"
    library.parent.mkdir()
    executable.write_bytes(b"MZ-provider-host-bootstrap")
    library.write_bytes(b"runtime")
    files = [
        {
            "path": path.relative_to(package).as_posix(),
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in (executable, library)
    ]
    manifest = package / "keeper-provider-host-package-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "KeeperProviderHost",
                "version": "1.7.1",
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    installer = ProviderHostInstaller(
        tmp_path / "installed", tmp_path / "startup"
    )
    installer.install(
        executable,
        version="1.7.1",
        expected_package_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )
    return ProviderHostBootstrap(
        installer=installer,
        signer=_PublicTestSigner(HOST),
        user_binding=UserBinding(SID, 1, str((tmp_path / "profile").resolve())),
        authority_protocol_version=7,
        authority_schema_version=6,
        service_key_id="keeper-authority:test",
        authenticode_observer=lambda path: {
            "certificate_thumbprint": None,
            "publisher_subject": None,
            "source": "windows-authenticode",
            "status": "NotSigned",
        },
        authority_verifier_factory=lambda value: AUTHORITY,
    )


def _authority_not_installed_status() -> dict[str, Any]:
    return {
        "founder_action_required": "INSTALL_PROVIDER_HOST",
        "installed": False,
        "online": False,
        "protocol": "keeper-provider-host/1",
        "protocol_compatible": True,
        "provider_state": "UNAVAILABLE",
        "state": "NOT_INSTALLED",
    }


def _update_bootstrap_package(
    bootstrap: ProviderHostBootstrap, tmp_path: Path
) -> str:
    package = tmp_path / "updated-package"
    package.mkdir()
    executable = package / "KeeperProviderHost.exe"
    library = package / "lib" / "runtime.dll"
    library.parent.mkdir()
    executable.write_bytes(b"MZ-provider-host-bootstrap-1.7.7")
    library.write_bytes(b"runtime-1.7.7")
    files = [
        {
            "path": path.relative_to(package).as_posix(),
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in (executable, library)
    ]
    manifest = package / "keeper-provider-host-package-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "KeeperProviderHost",
                "version": "1.7.7",
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    manifest_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    bootstrap.installer.update(
        executable,
        version="1.7.7",
        expected_package_sha256=manifest_digest,
        drain=lambda: None,
    )
    return manifest_digest


def _capability(
    proposal: Mapping[str, Any],
    *,
    action: str = "ENROLL_PROVIDER_HOST",
    generation: int = 1,
    suffix: str | None = None,
) -> dict[str, Any]:
    digest = structured_digest(proposal)
    return make_test_founder_capability(
        ENROLLMENT_SYSTEM_PROJECT,
        generation,
        suffix or action.casefold(),
        charter_id=ENROLLMENT_SYSTEM_CHARTER,
        claim_overrides={
            "charter_revision": 1,
            "authorization_kind": "PROVIDER_HOST_ENROLLMENT",
            "protected_action": action,
            "action_digest": digest,
            "founder_principal_sid": SID,
        },
    )


def _proof(begin: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, Any]:
    grant = begin["grant"]
    grant_payload = grant["payload"]
    now = datetime.now(UTC)
    return HOST.sign(
        ENROLLMENT_PROOF_PURPOSE,
        {
            "authority_id": grant_payload["authority_id"],
            "challenge": grant_payload["challenge"],
            "enrollment_generation": grant_payload["enrollment_generation"],
            "enrollment_id": begin["enrollment_id"],
            "grant_digest": begin["grant_digest"],
            "host_id": HOST.identity,
            "host_public_key_id": HOST.key_id,
            "issued_at": now.isoformat(),
            "nonce": "host-proof-nonce",
            "proposal_digest": structured_digest(proposal),
            "sequence": 1,
        },
    )


def test_enrollment_deadlock_is_removed_without_provider_binding(tmp_path: Path) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    proposal = _proposal(tmp_path)
    exact_capability = _capability(proposal)
    begin = coordinator.begin(
        {"proposal": proposal, "founder_capability": exact_capability}, SID
    )
    retried = coordinator.begin(
        {"proposal": proposal, "founder_capability": exact_capability}, SID
    )
    assert retried["grant_digest"] == begin["grant_digest"]
    assert retried["grant"] == begin["grant"]
    assert begin["state"] == "PENDING"
    assert coordinator.status()["state"] == "ENROLLMENT_PENDING"
    exact_proof = _proof(begin, proposal)
    completed = coordinator.complete(
        {"enrollment_id": begin["enrollment_id"], "proof": exact_proof},
        SID,
    )
    assert completed["state"] == "ACTIVE"
    assert observer.activations == [begin["enrollment_id"]]
    receipt = completed["receipt"]["payload"]
    assert receipt["runtime_configuration"].get("provider_binding") is None
    assert receipt["runtime_configuration"].get("provider_bindings") is None


def test_supported_protocol_operations_complete_enrollment_without_config_edits(
    tmp_path: Path,
) -> None:
    observer = _Observer()
    core = AuthorityServiceCore(tmp_path / "service")
    coordinator = ProviderHostEnrollmentCoordinator(
        store=core.store,
        service_key_id="keeper-authority:test",
        authority_protocol_version=7,
        authority_schema_version=6,
        founder_verifier=TestFounderCapabilityVerifier(),
        authority_signer=AUTHORITY,
        authority_public_identity=_public(AUTHORITY),
        proposal_observer=observer,
        activate=observer.activate,
        deactivate=observer.deactivate,
        host_verifier_factory=lambda value: HOST,
    )
    core.configure_provider_host_enrollment(coordinator)
    client = TestAuthorityServiceClient(
        lambda request: core.dispatch(request, SID)
    )
    proposal = _proposal(tmp_path)
    begun = client.begin_provider_host_enrollment(
        founder_capability=_capability(proposal), proposal=proposal
    )
    completed = client.complete_provider_host_enrollment(
        str(begun["enrollment_id"]), _proof(begun, proposal)
    )
    assert completed["state"] == "ACTIVE"
    assert client.provider_host_enrollment_status()["state"] == "ENROLLED_OFFLINE"
    assert observer.activations == [begun["enrollment_id"]]


def test_founder_cancellation_leaves_no_partial_enrollment(
    tmp_path: Path,
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    bootstrap = _installed_bootstrap(tmp_path)
    client = ProviderHostEnrollmentClient(
        authority=_AuthorityAdapter(coordinator),
        authenticator=_CancelledAuthenticator(principal_sid=SID),
        bootstrap=bootstrap,
    )
    with pytest.raises(PermissionError, match="canceled"):
        client.enroll(generation=1)
    assert not bootstrap.pending_path.exists()
    assert bootstrap.status()["state"] == "INSTALLED_UNENROLLED"
    assert coordinator.store.list_records("provider_host_enrollments") == []


def test_founder_authorized_proposal_cannot_be_silently_overwritten(
    tmp_path: Path,
) -> None:
    bootstrap = _installed_bootstrap(tmp_path)
    proposal = bootstrap.create_proposal(generation=1)
    bootstrap.store_founder_capability(_capability(proposal))
    before = bootstrap.pending_path.read_bytes()

    with pytest.raises(PermissionError, match="checkpoint must be resolved"):
        bootstrap.create_proposal(generation=1)

    assert bootstrap.pending_path.read_bytes() == before
    pending = json.loads(before)
    assert pending["proposal_digest"] == structured_digest(proposal)
    assert isinstance(pending["founder_capability"], dict)


def test_stale_authorized_proposal_requires_exact_authority_absence_and_new_package(
    tmp_path: Path,
) -> None:
    bootstrap = _installed_bootstrap(tmp_path)
    proposal = bootstrap.create_proposal(generation=1)
    bootstrap.store_founder_capability(_capability(proposal))
    before = bootstrap.pending_path.read_bytes()
    wrong_status = dict(_authority_not_installed_status())
    wrong_status["state"] = "ENROLLMENT_PENDING"

    with pytest.raises(PermissionError, match="does not prove"):
        bootstrap.prepare_new_enrollment(wrong_status)
    with pytest.raises(PermissionError, match="package binding differs"):
        bootstrap.prepare_new_enrollment(_authority_not_installed_status())

    assert bootstrap.pending_path.read_bytes() == before
    assert list(
        bootstrap.installer.state.glob(
            "provider-host-enrollment-superseded-*.json"
        )
    ) == []


def test_stale_authorized_proposal_is_durably_superseded_before_new_proposal(
    tmp_path: Path,
) -> None:
    bootstrap = _installed_bootstrap(tmp_path)
    proposal = bootstrap.create_proposal(generation=1)
    bootstrap.store_founder_capability(_capability(proposal))
    prior = json.loads(bootstrap.pending_path.read_text(encoding="utf-8"))
    prior_digest = structured_digest(prior)
    replacement_manifest = _update_bootstrap_package(bootstrap, tmp_path)

    result = bootstrap.prepare_new_enrollment(_authority_not_installed_status())

    assert result is not None
    assert result["state"] == "SUPERSEDED"
    assert result["proposal_digest"] == structured_digest(proposal)
    assert result["prior_checkpoint_digest"] == prior_digest
    assert not bootstrap.pending_path.exists()
    archive = Path(str(result["archive_path"]))
    archived = json.loads(archive.read_text(encoding="utf-8"))
    assert archived["state"] == "SUPERSEDED"
    assert archived["prior_checkpoint"] == prior
    assert archived["prior_checkpoint_digest"] == prior_digest
    assert archived["replacement_manifest_sha256"] == replacement_manifest
    assert archived["authority_status"] == _authority_not_installed_status()

    replacement = bootstrap.create_proposal(generation=1)
    assert structured_digest(replacement) != structured_digest(proposal)
    assert json.loads(archive.read_text(encoding="utf-8")) == archived


def test_supersession_archive_survives_interruption_before_pending_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap = _installed_bootstrap(tmp_path)
    proposal = bootstrap.create_proposal(generation=1)
    bootstrap.store_founder_capability(_capability(proposal))
    _update_bootstrap_package(bootstrap, tmp_path)
    original_unlink = Path.unlink
    calls = 0

    def interrupted_unlink(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal calls
        if path == bootstrap.pending_path and calls == 0:
            calls += 1
            raise OSError("simulated interruption before pending unlink")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", interrupted_unlink)
    with pytest.raises(OSError, match="simulated interruption"):
        bootstrap.prepare_new_enrollment(_authority_not_installed_status())
    assert bootstrap.pending_path.exists()
    archives = list(
        bootstrap.installer.state.glob(
            "provider-host-enrollment-superseded-*.json"
        )
    )
    assert len(archives) == 1

    result = bootstrap.prepare_new_enrollment(_authority_not_installed_status())
    assert result is not None
    assert not bootstrap.pending_path.exists()
    assert Path(str(result["archive_path"])) == archives[0]


def test_interrupted_unauthorized_replacement_proposal_retries_supported_flow(
    tmp_path: Path,
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    bootstrap = _installed_bootstrap(tmp_path)
    stale = bootstrap.create_proposal(generation=1)
    bootstrap.store_founder_capability(_capability(stale))
    replacement_manifest = _update_bootstrap_package(bootstrap, tmp_path)
    bootstrap.prepare_new_enrollment(_authority_not_installed_status())

    # Simulate termination after the replacement proposal was persisted but
    # before the interactive Founder authenticator returned.
    interrupted = bootstrap.create_proposal(generation=1)
    interrupted_checkpoint = json.loads(
        bootstrap.pending_path.read_text(encoding="utf-8")
    )
    assert interrupted_checkpoint["founder_capability"] is None

    client = ProviderHostEnrollmentClient(
        authority=_AuthorityAdapter(coordinator),
        authenticator=TestFounderAuthenticator(principal_sid=SID),
        bootstrap=bootstrap,
    )
    result = client.enroll(generation=1)

    assert result["state"] == "ACTIVE"
    assert observer.activations == [result["enrollment_id"]]
    archives = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in bootstrap.installer.state.glob(
            "provider-host-enrollment-superseded-*.json"
        )
    ]
    interrupted_archive = next(
        record
        for record in archives
        if record["reason"] == "UNAUTHORIZED_PROPOSAL_INTERRUPTED"
    )
    assert interrupted_archive["prior_checkpoint"] == interrupted_checkpoint
    assert interrupted_archive["prior_checkpoint_digest"] == structured_digest(
        interrupted_checkpoint
    )
    assert interrupted_archive["prior_manifest_sha256"] == replacement_manifest
    assert interrupted_archive["replacement_manifest_sha256"] == replacement_manifest
    assert interrupted_archive["authority_status"] == _authority_not_installed_status()
    assert interrupted_archive["prior_checkpoint"]["proposal_digest"] == (
        structured_digest(interrupted)
    )


def test_supported_supersession_serializes_resume_and_preserves_durable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    bootstrap = _installed_bootstrap(tmp_path)
    stale = bootstrap.create_proposal(generation=1)
    bootstrap.store_founder_capability(_capability(stale))
    _update_bootstrap_package(bootstrap, tmp_path)
    enrolling = ProviderHostEnrollmentClient(
        authority=_AuthorityAdapter(coordinator),
        authenticator=TestFounderAuthenticator(principal_sid=SID),
        bootstrap=bootstrap,
    )
    resuming = ProviderHostEnrollmentClient(
        authority=_AuthorityAdapter(coordinator),
        authenticator=TestFounderAuthenticator(principal_sid=SID),
        bootstrap=bootstrap,
    )
    reached_unlink = threading.Event()
    allow_unlink = threading.Event()
    resume_started = threading.Event()
    resume_finished = threading.Event()
    original_unlink = Path.unlink
    blocked_once = False

    def blocking_unlink(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal blocked_once
        if path == bootstrap.pending_path and not blocked_once:
            blocked_once = True
            reached_unlink.set()
            assert allow_unlink.wait(timeout=5)
        original_unlink(path, *args, **kwargs)

    def resume() -> dict[str, Any]:
        resume_started.set()
        try:
            return resuming.resume_authorization()
        finally:
            resume_finished.set()

    monkeypatch.setattr(Path, "unlink", blocking_unlink)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replacement = pool.submit(enrolling.enroll, generation=1)
        assert reached_unlink.wait(timeout=5)
        competing_resume = pool.submit(resume)
        assert resume_started.wait(timeout=5)
        assert not resume_finished.wait(timeout=0.1)
        assert coordinator.status()["state"] == "NOT_INSTALLED"
        allow_unlink.set()
        enrolled = replacement.result(timeout=10)
        with pytest.raises(PermissionError, match="checkpoint is invalid"):
            competing_resume.result(timeout=10)

    assert enrolled["state"] == "ACTIVE"
    assert observer.activations == [enrolled["enrollment_id"]]
    assert coordinator.status()["state"] == "ENROLLED_OFFLINE"
    assert bootstrap.status()["state"] == "ENROLLED_OFFLINE"


def test_enrollment_rejects_missing_founder_tamper_replay_and_wrong_sid(tmp_path: Path) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    proposal = _proposal(tmp_path)
    with pytest.raises(PermissionError, match="capability"):
        coordinator.begin({"proposal": proposal, "founder_capability": {}}, SID)
    wrong = dict(proposal)
    wrong["signature"] = str(proposal["signature"])[:-2] + "AA"
    with pytest.raises(PermissionError, match="signature"):
        coordinator.begin(
            {"proposal": wrong, "founder_capability": _capability(wrong)}, SID
        )
    with pytest.raises(PermissionError, match="identity differs|user differs"):
        coordinator.begin(
            {"proposal": proposal, "founder_capability": _capability(proposal)},
            "S-1-5-21-WRONG",
        )
    begin = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    second_proposal = _proposal(tmp_path / "other")
    with pytest.raises(PermissionError, match="already unresolved|replayed"):
        coordinator.begin(
            {
                "proposal": second_proposal,
                "founder_capability": _capability(second_proposal),
            },
            SID,
        )
    proof = _proof(begin, proposal)
    first = coordinator.complete(
        {"enrollment_id": begin["enrollment_id"], "proof": proof}, SID
    )
    second = coordinator.reconcile(
        {"enrollment_id": begin["enrollment_id"], "proof": proof}, SID
    )
    assert second["receipt_digest"] == first["receipt_digest"]
    replaced = dict(proof)
    replaced["signature"] = str(proof["signature"])[::-1]
    with pytest.raises(PermissionError, match="differs|signature"):
        coordinator.reconcile(
            {"enrollment_id": begin["enrollment_id"], "proof": replaced}, SID
        )


def test_enrollment_revocation_requires_exact_new_founder_capability(tmp_path: Path) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    proposal = _proposal(tmp_path)
    begin = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    exact_proof = _proof(begin, proposal)
    completed = coordinator.complete(
        {"enrollment_id": begin["enrollment_id"], "proof": exact_proof},
        SID,
    )
    binding = {
        "action": "REVOKE_PROVIDER_HOST",
        "enrollment_id": begin["enrollment_id"],
        "receipt_digest": structured_digest(completed["receipt"]),
    }
    revocation = make_test_founder_capability(
        ENROLLMENT_SYSTEM_PROJECT,
        2,
        "revoke",
        charter_id=ENROLLMENT_SYSTEM_CHARTER,
        claim_overrides={
            "charter_revision": 1,
            "authorization_kind": "PROVIDER_HOST_ENROLLMENT",
            "protected_action": "REVOKE_PROVIDER_HOST",
            "action_digest": structured_digest(binding),
            "founder_principal_sid": SID,
        },
    )
    result = coordinator.revoke(
        {"enrollment_id": begin["enrollment_id"], "founder_capability": revocation},
        SID,
    )
    assert result["state"] == "REVOKED"
    assert observer.deactivations == [begin["enrollment_id"]]
    repeated = coordinator.revoke(
        {"enrollment_id": begin["enrollment_id"], "founder_capability": revocation},
        SID,
    )
    assert repeated == result
    assert observer.deactivations == [begin["enrollment_id"]]
    conflicting = make_test_founder_capability(
        ENROLLMENT_SYSTEM_PROJECT,
        2,
        "revoke-conflict",
        charter_id=ENROLLMENT_SYSTEM_CHARTER,
        claim_overrides={
            "charter_revision": 1,
            "authorization_kind": "PROVIDER_HOST_ENROLLMENT",
            "protected_action": "REVOKE_PROVIDER_HOST",
            "action_digest": structured_digest(binding),
            "founder_principal_sid": SID,
        },
    )
    # A fresh, exact Founder authentication may retrieve the already durable
    # denial after a lost response; it cannot change or widen the revocation.
    assert coordinator.revoke(
        {
            "enrollment_id": begin["enrollment_id"],
            "founder_capability": conflicting,
        },
        SID,
    ) == result


def test_revocation_transition_failure_stays_uncertain_and_cannot_reactivate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    proposal = _proposal(tmp_path)
    begin = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    exact_proof = _proof(begin, proposal)
    completed = coordinator.complete(
        {"enrollment_id": begin["enrollment_id"], "proof": exact_proof},
        SID,
    )
    binding = {
        "action": "REVOKE_PROVIDER_HOST",
        "enrollment_id": begin["enrollment_id"],
        "receipt_digest": structured_digest(completed["receipt"]),
    }
    capability = make_test_founder_capability(
        ENROLLMENT_SYSTEM_PROJECT,
        2,
        "revoke-interrupted",
        charter_id=ENROLLMENT_SYSTEM_CHARTER,
        claim_overrides={
            "charter_revision": 1,
            "authorization_kind": "PROVIDER_HOST_ENROLLMENT",
            "protected_action": "REVOKE_PROVIDER_HOST",
            "action_digest": structured_digest(binding),
            "founder_principal_sid": SID,
        },
    )
    original = coordinator.store.transition_provider_host_enrollment
    calls = 0

    def fail_final_transition(*args: object, **kwargs: object) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated persistence interruption")
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        coordinator.store,
        "transition_provider_host_enrollment",
        fail_final_transition,
    )
    with pytest.raises(OSError, match="persistence interruption"):
        coordinator.revoke(
            {
                "enrollment_id": begin["enrollment_id"],
                "founder_capability": capability,
            },
            SID,
        )
    stored = coordinator.store.get(
        "provider_host_enrollments", begin["enrollment_id"]
    )
    assert stored is not None
    assert stored["service_state"] == "UNCERTAIN"
    assert stored["uncertainty_kind"] == "REVOCATION"
    restarted_observer = _Observer()
    restarted = ProviderHostEnrollmentCoordinator(
        store=coordinator.store,
        service_key_id="keeper-authority:test",
        authority_protocol_version=7,
        authority_schema_version=6,
        founder_verifier=TestFounderCapabilityVerifier(),
        authority_signer=AUTHORITY,
        authority_public_identity=_public(AUTHORITY),
        proposal_observer=restarted_observer,
        activate=restarted_observer.activate,
        deactivate=restarted_observer.deactivate,
        host_verifier_factory=lambda value: HOST,
    )
    restarted.activate_current()
    assert restarted_observer.activations == []
    with pytest.raises(PermissionError, match="cannot be reconciled"):
        restarted.reconcile(
            {
                "enrollment_id": begin["enrollment_id"],
                "proof": exact_proof,
            },
            SID,
        )


def test_lost_revocation_response_accepts_fresh_exact_founder_reconciliation(
    tmp_path: Path,
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    (tmp_path / "host").mkdir()
    bootstrap = _installed_bootstrap(tmp_path / "host")
    client = ProviderHostEnrollmentClient(
        authority=_AuthorityAdapter(coordinator),
        authenticator=TestFounderAuthenticator(principal_sid=SID),
        bootstrap=bootstrap,
    )
    enrolled = client.enroll(generation=1)
    receipt_digest = str(enrolled["receipt_digest"])
    first_binding = {
        "action": "REVOKE_PROVIDER_HOST",
        "enrollment_id": enrolled["enrollment_id"],
        "receipt_digest": receipt_digest,
    }
    first = _capability(
        first_binding,
        action="REVOKE_PROVIDER_HOST",
        generation=2,
        suffix="lost-revocation-response",
    )
    coordinator.revoke(
        {"enrollment_id": enrolled["enrollment_id"], "founder_capability": first},
        SID,
    )
    assert bootstrap.status()["state"] == "ENROLLED_OFFLINE"
    recovered = client.revoke(
        enrollment_id=str(enrolled["enrollment_id"]),
        receipt_digest=receipt_digest,
        generation=2,
    )
    assert recovered["state"] == "REVOKED"
    assert bootstrap.status()["state"] == "REVOKED"


def test_bootstrap_installed_unenrolled_then_exact_receipt_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    bootstrap = _installed_bootstrap(tmp_path)
    assert bootstrap.status()["state"] == "INSTALLED_UNENROLLED"
    proposal = bootstrap.create_proposal(generation=1)
    begun = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    proof = bootstrap.prove_grant(begun["grant"])
    completed = coordinator.complete(
        {"enrollment_id": begun["enrollment_id"], "proof": proof}, SID
    )
    committed = bootstrap.commit_receipt(completed["receipt"])
    assert committed["state"] == "ACTIVE"
    assert bootstrap.status()["state"] == "ENROLLED_OFFLINE"
    receipt = json.loads(bootstrap.config_path.read_text(encoding="utf-8"))
    config = receipt["payload"]["runtime_configuration"]
    assert config["schema_version"] == 2
    assert "provider_binding" not in config
    assert "provider_bindings" not in config
    monkeypatch.setattr(
        "keeper.provider_host.cli.RsaPublicIdentity.from_configuration",
        lambda value: _VerifierHolder(),
    )
    assert _config(bootstrap.config_path) == config


def test_bootstrap_unsigned_runtime_and_expired_grant_reject(tmp_path: Path) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    bootstrap = _installed_bootstrap(tmp_path)
    proposal = bootstrap.create_proposal(generation=1)
    begun = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    unsigned_runtime = tmp_path / "unsigned-runtime.json"
    unsigned_runtime.write_text(
        json.dumps(observer.provider_host_runtime_configuration(
            proposal["payload"],
            enrollment_id=str(begun["enrollment_id"]),
            authority_id=AUTHORITY.identity,
            authority_public_identity=_public(AUTHORITY),
        )),
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="configuration"):
        _config(unsigned_runtime)
    expired = json.loads(json.dumps(begun["grant"]))
    expired["payload"]["expires_at"] = (
        datetime.now(UTC) - timedelta(seconds=1)
    ).isoformat()
    expired = AUTHORITY.sign(
        expired["purpose"], expired["payload"]
    )
    with pytest.raises(PermissionError, match="lifetime"):
        bootstrap.prove_grant(expired)


def test_bootstrap_tamper_and_cross_receipt_fail_closed(tmp_path: Path) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    bootstrap = _installed_bootstrap(tmp_path)
    proposal = bootstrap.create_proposal(generation=1)
    begun = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    altered = json.loads(json.dumps(begun["grant"]))
    altered["payload"]["challenge"] = "wrong"
    with pytest.raises(PermissionError, match="signature"):
        bootstrap.prove_grant(altered)
    proof = bootstrap.prove_grant(begun["grant"])
    completed = coordinator.complete(
        {"enrollment_id": begun["enrollment_id"], "proof": proof}, SID
    )
    altered_receipt = json.loads(json.dumps(completed["receipt"]))
    altered_receipt["payload"]["proof_digest"] = "0" * 64
    with pytest.raises(PermissionError, match="signature"):
        bootstrap.commit_receipt(altered_receipt)
    assert not bootstrap.config_path.exists()


def test_supported_client_requires_founder_and_removes_manual_config_deadlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    bootstrap = _installed_bootstrap(tmp_path)
    client = ProviderHostEnrollmentClient(
        authority=_AuthorityAdapter(coordinator),
        authenticator=TestFounderAuthenticator(principal_sid=SID),
        bootstrap=bootstrap,
    )
    result = client.enroll(generation=1)
    assert result["state"] == "ACTIVE"
    assert observer.activations == [result["enrollment_id"]]
    assert bootstrap.status()["provider_state"] == "NO_QUALIFIED_PROVIDERS"
    with pytest.raises(PermissionError, match="already active"):
        bootstrap.create_proposal(generation=2)
    revoked = client.revoke(
        enrollment_id=str(result["enrollment_id"]),
        receipt_digest=str(result["receipt_digest"]),
        generation=2,
    )
    assert revoked["state"] == "REVOKED"
    assert bootstrap.status()["state"] == "REVOKED"
    assert bootstrap.revocation_path.is_file()
    monkeypatch.setattr(
        "keeper.provider_host.cli.RsaPublicIdentity.from_configuration",
        lambda value: _VerifierHolder(),
    )
    assert _revoked_status(bootstrap.config_path) == {
        "enrollment_id": result["enrollment_id"],
        "founder_action_required": "CREATE_NEW_PROVIDER_HOST_ENROLLMENT",
        "installed": True,
        "online": False,
        "provider_state": "UNAVAILABLE",
        "state": "REVOKED",
    }
    with pytest.raises(PermissionError, match="generation is stale"):
        client.enroll(generation=1)
    reenrolled = client.enroll(generation=2)
    assert reenrolled["state"] == "ACTIVE"
    assert reenrolled["enrollment_id"] != result["enrollment_id"]
    assert not bootstrap.revocation_path.exists()
    assert bootstrap.status()["state"] == "ENROLLED_OFFLINE"


def test_production_observer_remeasures_exact_user_host_before_enrollment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import keeper.authority_service.observer as observer_module

    profile = tmp_path / "Founder"
    install = (
        profile
        / "AppData"
        / "Local"
        / "Programs"
        / "DarkSage"
        / "KeeperProviderHost"
    )
    startup = (
        profile
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )
    package = tmp_path / "observer-package"
    package.mkdir()
    package_executable = package / "KeeperProviderHost.exe"
    package_executable.write_bytes(b"MZ-provider-host-production-observer")
    manifest = package / "keeper-provider-host-package-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "KeeperProviderHost",
                "version": "1.7.1",
                "files": [
                    {
                        "path": "KeeperProviderHost.exe",
                        "size": package_executable.stat().st_size,
                        "sha256": hashlib.sha256(
                            package_executable.read_bytes()
                        ).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    installer = ProviderHostInstaller(install, startup)
    installed = installer.install(
        package_executable,
        version="1.7.1",
        expected_package_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )
    executable = Path(installed.artifact_path)
    state = installer.state
    output = install / "output"
    output.mkdir()
    credential = tmp_path / "credential"
    credential.write_bytes(b"fixture")
    observer = ServiceProviderObserver(
        tmp_path / "providers", tmp_path / "evidence", "unused", credential, SID
    )
    observer._local.client_token = 42
    observer._local.client_binding = _FakeClientBinding()
    monkeypatch.setattr(observer_module, "require_impersonation_level", lambda token: 2)
    monkeypatch.setattr(observer_module, "token_user_sid_string", lambda token: SID)
    monkeypatch.setattr(observer_module, "token_session_id", lambda token: 1)
    monkeypatch.setattr(
        observer_module,
        "windows_session_is_active",
        lambda session: WindowsSessionQueryResult(
            WindowsSessionQueryStatus.ACTIVE, state=0
        ),
    )
    monkeypatch.setattr(
        observer_module,
        "authenticated_client_environment",
        lambda token: {"USERPROFILE": str(profile), "PATH": str(tmp_path)},
    )
    monkeypatch.setattr(
        observer_module,
        "authenticated_client_profile_path",
        lambda token, value: str(Path(value).resolve(strict=True)),
    )
    monkeypatch.setattr(
        observer_module,
        "_authenticated_client_provider_host_path_observation",
        lambda token, **values: observer_module._read_provider_host_path_observation(
            **values
        ),
    )
    signature = {
        "certificate_thumbprint": None,
        "publisher_subject": None,
        "source": "windows-authenticode",
        "status": "NotSigned",
    }
    monkeypatch.setattr(
        observer_module,
        "authenticode_enrollment_binding",
        lambda path: dict(signature),
    )
    stat = executable.stat()
    host_id, host_key_name = stable_host_identity(
        SID, installed.package_sha256
    )
    pipe_suffix = hashlib.sha256(
        (host_id + ":" + SID).encode("utf-8")
    ).hexdigest()[:24]
    proposal = _proposal(tmp_path)["payload"]
    proposal.update(
        {
            "host_id": host_id,
            "host_key_name": host_key_name,
            "installation": {
                "authenticode_binding": signature,
                "executable_file_identity": {
                    "device_id": stat.st_dev,
                    "file_id": stat.st_ino,
                    "modified_ns": stat.st_mtime_ns,
                    "schema_version": 1,
                    "size": stat.st_size,
                },
                "executable_path": str(executable.resolve()),
                "executable_sha256": hashlib.sha256(
                    executable.read_bytes()
                ).hexdigest(),
                "executable_size": stat.st_size,
                "install_root": str(install.resolve()),
                "manifest_sha256": installed.package_sha256,
                "package_version": "1.7.1",
            },
            "output_root": str(output.resolve()),
            "pipe_name": rf"\\.\pipe\KeeperProviderHost-{pipe_suffix}",
            "state_root": str(state.resolve()),
            "user_binding": {
                "profile_path": str(profile.resolve()),
                "session_id": 1,
                "user_sid": SID,
            },
        }
    )
    assert observer.validate_provider_host_enrollment_proposal(proposal, SID) == proposal
    wrong = json.loads(json.dumps(proposal))
    wrong["installation"]["executable_sha256"] = "0" * 64
    with pytest.raises(PermissionError, match="installed package differs"):
        observer.validate_provider_host_enrollment_proposal(wrong, SID)
    wrong = json.loads(json.dumps(proposal))
    wrong["user_binding"]["session_id"] = 2
    with pytest.raises(PermissionError, match="binding differs"):
        observer.validate_provider_host_enrollment_proposal(wrong, SID)


def test_provider_host_path_validation_uses_only_disposable_client_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ctypes
    import keeper.authority_service.observer as observer_module
    import keeper.authority_service.restricted_process as restricted_process_module

    events: list[str] = []
    local = threading.local()
    service_thread = threading.get_ident()

    class Kernel32:
        @staticmethod
        def GetCurrentThread() -> int:
            return threading.get_ident()

        @staticmethod
        def CloseHandle(handle: object) -> bool:
            del handle
            return True

    class Advapi32:
        @staticmethod
        def OpenThreadToken(
            thread: int, access: int, open_as_self: bool, output: object
        ) -> bool:
            del thread, output
            assert access == 0x0008
            assert open_as_self is True
            if getattr(local, "impersonating", False):
                events.append("token-present")
                return True
            ctypes.set_last_error(1008)
            events.append("no-token")
            return False

        @staticmethod
        def ImpersonateLoggedOnUser(token: int) -> bool:
            assert token == 42
            assert threading.get_ident() != service_thread
            local.impersonating = True
            events.append("impersonate")
            return True

        @staticmethod
        def RevertToSelf() -> bool:
            events.append("revert")
            local.impersonating = False
            return True

    def read_only_observation(**values: object) -> dict[str, Any]:
        assert values == {
            "profile": r"C:\Users\Founder",
            "installation": {"executable_path": r"C:\Host\KeeperProviderHost.exe"},
            "observed_sid": SID,
        }
        assert getattr(local, "impersonating", False)
        assert threading.get_ident() != service_thread
        events.append("read-only-host-paths")
        return {"validated": True}

    monkeypatch.setattr(
        restricted_process_module, "_advapi32", lambda: Advapi32()
    )
    monkeypatch.setattr(
        restricted_process_module, "_kernel32", lambda: Kernel32()
    )
    monkeypatch.setattr(
        observer_module, "require_impersonation_level", lambda token: 2
    )
    monkeypatch.setattr(
        observer_module,
        "_read_provider_host_path_observation",
        read_only_observation,
    )

    result = observer_module._authenticated_client_provider_host_path_observation(
        42,
        profile=r"C:\Users\Founder",
        installation={"executable_path": r"C:\Host\KeeperProviderHost.exe"},
        observed_sid=SID,
    )

    assert result == {"validated": True}
    assert events == [
        "no-token",
        "no-token",
        "impersonate",
        "read-only-host-paths",
        "revert",
        "no-token",
        "no-token",
    ]


@pytest.mark.parametrize("failure", ["impersonate", "revert"])
def test_provider_host_path_validation_fails_closed_without_returning_observation(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    import ctypes
    import keeper.authority_service.observer as observer_module
    import keeper.authority_service.restricted_process as restricted_process_module

    events: list[str] = []
    local = threading.local()

    class Kernel32:
        @staticmethod
        def GetCurrentThread() -> int:
            return threading.get_ident()

        @staticmethod
        def CloseHandle(handle: object) -> bool:
            del handle
            return True

    class Advapi32:
        @staticmethod
        def OpenThreadToken(
            thread: int, access: int, open_as_self: bool, output: object
        ) -> bool:
            del thread, access, open_as_self, output
            if getattr(local, "impersonating", False):
                events.append("token-present")
                return True
            ctypes.set_last_error(1008)
            events.append("no-token")
            return False

        @staticmethod
        def ImpersonateLoggedOnUser(token: int) -> bool:
            del token
            events.append("impersonate")
            if failure == "impersonate":
                ctypes.set_last_error(5)
                return False
            local.impersonating = True
            return True

        @staticmethod
        def RevertToSelf() -> bool:
            events.append("revert")
            if failure == "revert":
                ctypes.set_last_error(5)
                return False
            local.impersonating = False
            return True

    def read_only_observation(**values: object) -> dict[str, Any]:
        del values
        events.append("read-only-host-paths")
        return {"must_not_escape": True}

    monkeypatch.setattr(
        restricted_process_module, "_advapi32", lambda: Advapi32()
    )
    monkeypatch.setattr(
        restricted_process_module, "_kernel32", lambda: Kernel32()
    )
    monkeypatch.setattr(
        observer_module, "require_impersonation_level", lambda token: 2
    )
    monkeypatch.setattr(
        observer_module,
        "_read_provider_host_path_observation",
        read_only_observation,
    )

    with pytest.raises((PermissionError, RuntimeError)):
        observer_module._authenticated_client_provider_host_path_observation(
            42,
            profile=r"C:\Users\Founder",
            installation={},
            observed_sid=SID,
        )
    if failure == "impersonate":
        assert "read-only-host-paths" not in events
    else:
        assert events.count("read-only-host-paths") == 1
        assert events.count("revert") == 1


def test_lost_enrollment_authorization_response_resumes_exact_grant(
    tmp_path: Path,
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    bootstrap = _installed_bootstrap(tmp_path)
    client = ProviderHostEnrollmentClient(
        authority=_LostBeginAdapter(coordinator),
        authenticator=TestFounderAuthenticator(principal_sid=SID),
        bootstrap=bootstrap,
    )
    with pytest.raises(OSError, match="lost enrollment"):
        client.enroll(generation=1)
    assert bootstrap.status()["state"] == "ENROLLMENT_PROPOSED"
    resumed = client.resume_authorization()
    assert resumed["state"] == "ACTIVE"
    assert observer.activations == [resumed["enrollment_id"]]


def test_expired_pending_enrollment_reconciles_without_host_proof(
    tmp_path: Path,
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    proposal = _proposal(tmp_path)
    begun = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    coordinator.now = lambda: datetime.now(UTC) + timedelta(minutes=5)
    result = coordinator.reconcile(
        {"enrollment_id": begun["enrollment_id"], "proof": None}, SID
    )
    assert result == {
        "enrollment_id": begun["enrollment_id"],
        "state": "EXPIRED",
    }
    assert coordinator.status()["state"] == "ENROLLMENT_EXPIRED"


def test_activation_interruption_becomes_uncertain_and_reconciles_exact_proof(
    tmp_path: Path,
) -> None:
    observer = _FailOnceObserver()
    coordinator = _coordinator(tmp_path, observer)
    proposal = _proposal(tmp_path)
    begun = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    proof = _proof(begun, proposal)
    with pytest.raises(RuntimeError, match="uncertain"):
        coordinator.complete(
            {"enrollment_id": begun["enrollment_id"], "proof": proof}, SID
        )
    assert coordinator.status()["state"] == "UNCERTAIN"
    recovered = coordinator.reconcile(
        {"enrollment_id": begun["enrollment_id"], "proof": proof}, SID
    )
    assert recovered["state"] == "ACTIVE"
    assert observer.activations == [begun["enrollment_id"]]


def test_concurrent_conflicting_enrollment_proposals_have_one_winner(
    tmp_path: Path,
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    first = _proposal(tmp_path)
    second_payload = json.loads(json.dumps(first["payload"]))
    second_payload["proposal_nonce"] = "different-proposal-nonce"
    second = HOST.sign(first["purpose"], second_payload)
    barrier = threading.Barrier(2)

    def begin(proposal: dict[str, Any]) -> str:
        barrier.wait(timeout=5)
        try:
            result = coordinator.begin(
                {
                    "proposal": proposal,
                    "founder_capability": _capability(proposal),
                },
                SID,
            )
        except PermissionError:
            return "REJECTED"
        return str(result["state"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(begin, (first, second)))
    assert sorted(outcomes) == ["PENDING", "REJECTED"]
    assert coordinator.status()["state"] == "ENROLLMENT_PENDING"


def test_active_enrollment_rehydrates_exact_gateway_after_authority_restart(
    tmp_path: Path,
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    proposal = _proposal(tmp_path)
    begun = coordinator.begin(
        {"proposal": proposal, "founder_capability": _capability(proposal)}, SID
    )
    proof = _proof(begun, proposal)
    coordinator.complete(
        {"enrollment_id": begun["enrollment_id"], "proof": proof}, SID
    )
    restarted_observer = _Observer()
    restarted = _coordinator(tmp_path, restarted_observer)
    restarted.activate_current()
    assert restarted_observer.activations == [begun["enrollment_id"]]
    assert restarted.status()["state"] == "ENROLLED_OFFLINE"


def test_future_issued_and_conflicting_exact_replay_fail_closed(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path, _Observer())
    future = _proposal(tmp_path)
    future_payload = json.loads(json.dumps(future["payload"]))
    issued = datetime.now(UTC) + timedelta(seconds=30)
    future_payload["issued_at"] = issued.isoformat()
    future_payload["expires_at"] = (issued + timedelta(minutes=1)).isoformat()
    future = HOST.sign(future["purpose"], future_payload)
    with pytest.raises(PermissionError, match="lifetime"):
        coordinator.begin(
            {"proposal": future, "founder_capability": _capability(future)}, SID
        )

    proposal = _proposal(tmp_path / "valid")
    capability = _capability(proposal)
    first = coordinator.begin(
        {"proposal": proposal, "founder_capability": capability}, SID
    )
    assert first["state"] == "PENDING"
    conflicting = _capability(proposal, suffix="conflicting-enrollment")
    with pytest.raises(PermissionError, match="already unresolved"):
        coordinator.begin(
            {"proposal": proposal, "founder_capability": conflicting}, SID
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("authority_protocol_version", 6, "compatibility"),
        ("authority_schema_version", 5, "compatibility"),
        ("service_key_id", "keeper-authority:wrong", "compatibility"),
        ("host_protocol", "keeper-provider-host/0", "compatibility"),
    ],
)
def test_enrollment_downgrade_and_service_identity_mismatch_reject(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    observer = _Observer()
    coordinator = _coordinator(tmp_path, observer)
    proposal = _proposal(tmp_path)
    payload = json.loads(json.dumps(proposal["payload"]))
    payload[field] = value
    changed = HOST.sign(proposal["purpose"], payload)
    with pytest.raises(PermissionError, match=message):
        coordinator.begin(
            {"proposal": changed, "founder_capability": _capability(changed)}, SID
        )


def test_packaged_cli_exposes_supported_enrollment_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from keeper.provider_host import cli

    calls: list[tuple[str, object]] = []

    class EnrollmentSurface:
        def enroll(self, *, generation: int) -> dict[str, object]:
            calls.append(("enroll", generation))
            return {"state": "ACTIVE"}

        def resume_authorization(self) -> dict[str, object]:
            calls.append(("resume", None))
            return {"state": "ACTIVE"}

        def reconcile(self) -> dict[str, object]:
            calls.append(("reconcile", None))
            return {"state": "ACTIVE"}

        def reconcile_expired(self, enrollment_id: str) -> dict[str, object]:
            calls.append(("expired", enrollment_id))
            return {"state": "EXPIRED"}

        def revoke(
            self,
            *,
            enrollment_id: str,
            receipt_digest: str,
            generation: int,
        ) -> dict[str, object]:
            calls.append(
                ("revoke", (enrollment_id, receipt_digest, generation))
            )
            return {"state": "REVOKED"}

    monkeypatch.setattr(cli, "_enrollment_client_factory", EnrollmentSurface)
    assert cli.main(["enroll", "--generation", "1"]) == 0
    assert cli.main(["resume-enrollment"]) == 0
    assert cli.main(["reconcile-enrollment"]) == 0
    assert cli.main(
        ["reconcile-expired-enrollment", "--enrollment-id", "enrollment-1"]
    ) == 0
    digest = "a" * 64
    assert cli.main(
        [
            "revoke-enrollment",
            "--enrollment-id",
            "enrollment-1",
            "--receipt-digest",
            digest,
            "--generation",
            "2",
        ]
    ) == 0
    assert calls == [
        ("enroll", 1),
        ("resume", None),
        ("reconcile", None),
        ("expired", "enrollment-1"),
        ("revoke", ("enrollment-1", digest, 2)),
    ]
    assert '"state": "ACTIVE"' in capsys.readouterr().out


def test_production_enrollment_cli_fails_closed_on_factory_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from keeper.provider_host import cli

    def unavailable() -> ProviderHostEnrollmentClient:
        raise PermissionError("exact production enrollment unavailable")

    monkeypatch.setattr(cli, "_enrollment_client_factory", unavailable)
    assert cli.main(["enroll", "--generation", "1"]) == 2
    assert "exact production enrollment unavailable" in capsys.readouterr().err


def test_provider_host_accepts_only_exact_authority_release_contract() -> None:
    _validate_authority_compatibility(
        {
            "service_version": "1.7.7",
            "protocol_version": 7,
            "schema_version": 6,
        }
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("service_version", "1.7.6"),
        ("service_version", "1.7.8"),
        ("protocol_version", 6),
        ("protocol_version", 8),
        ("schema_version", 5),
        ("schema_version", 7),
    ],
)
def test_provider_host_rejects_authority_release_contract_mismatch(
    field: str, value: object
) -> None:
    diagnostics: dict[str, object] = {
        "service_version": "1.7.7",
        "protocol_version": 7,
        "schema_version": 6,
    }
    diagnostics[field] = value

    with pytest.raises(PermissionError, match="exact matching KeeperAuthority"):
        _validate_authority_compatibility(diagnostics)
