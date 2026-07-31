from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

import pytest

from keeper.authority_service.client import AuthorityServiceClient
from keeper.authority_service.core import AuthorityServiceCore
from keeper.authority_service.ipc_server import NamedPipeAuthorityServer
from keeper.authority_service.windows_identity import (
    WindowsTokenIdentity,
    current_process_sid,
)
from keeper.authority_service.restricted_process import (
    restricted_current_process_token,
    run_restricted_process,
)


@pytest.mark.skipif(os.name != "nt", reason="Windows named-pipe test")
def test_named_pipe_authenticates_client_and_serves_framed_request(
    tmp_path: Path,
) -> None:
    pipe_name = rf"\\.\pipe\KeeperAuthority-test-{uuid.uuid4().hex}"
    core = AuthorityServiceCore(tmp_path / "service")
    server = NamedPipeAuthorityServer(
        core, current_process_sid(), pipe_name=pipe_name
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    assert server.ready.wait(timeout=5)
    try:
        try:
            result = AuthorityServiceClient(
                pipe_name, timeout_seconds=5
            ).diagnostics()
        except PermissionError as error:
            if "restricted authority clients" in str(error):
                pytest.skip(
                    "Codex sandbox intentionally presents a restricted token"
                )
            raise
        assert result["service_version"] == "1.6.0"
        assert result["client_sid"] == current_process_sid()
    finally:
        server.stop()
        thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.mark.skipif(os.name != "nt", reason="Windows named-pipe test")
def test_named_pipe_rejects_wrong_os_identity(tmp_path: Path) -> None:
    pipe_name = rf"\\.\pipe\KeeperAuthority-test-{uuid.uuid4().hex}"
    core = AuthorityServiceCore(tmp_path / "service")
    server = NamedPipeAuthorityServer(
        core, "S-1-5-18", pipe_name=pipe_name
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    assert server.ready.wait(timeout=5)
    try:
        with pytest.raises(PermissionError, match="unauthorized"):
            AuthorityServiceClient(
                pipe_name, timeout_seconds=5
            ).diagnostics()
    finally:
        server.stop()
        thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.mark.skipif(os.name != "nt", reason="Windows named-pipe test")
def test_low_restricted_provider_cannot_connect_to_authority_pipe(
    tmp_path: Path,
) -> None:
    pipe_leaf = f"KeeperAuthority-test-{uuid.uuid4().hex}"
    pipe_name = rf"\\.\pipe\{pipe_leaf}"
    core = AuthorityServiceCore(tmp_path / "service")
    server = NamedPipeAuthorityServer(
        core, current_process_sid(), pipe_name=pipe_name
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    assert server.ready.wait(timeout=5)
    executable = Path(
        os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    try:
        try:
            with restricted_current_process_token() as token:
                result = run_restricted_process(
                    token,
                    [str(executable), "/d", "/c", "type", pipe_name],
                    executable,
                    tmp_path,
                    environment,
                    tmp_path / "provider-stdout.log",
                    tmp_path / "provider-stderr.log",
                    10,
                )
        except PermissionError as error:
            if "failed: 87" in str(error):
                pytest.skip("Codex sandbox token cannot derive another restricted token")
            raise
        assert result.exit_code != 0
        assert result.timed_out is False
        assert server.accepted_connections == 0
    finally:
        server.stop()
        thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.mark.parametrize(
    ("identity", "message"),
    [
        (
            WindowsTokenIdentity("S-1-5-21-1000", True, 8192),
            "restricted",
        ),
        (
            WindowsTokenIdentity("S-1-5-21-1000", False, 4096),
            "low-integrity",
        ),
        (
            WindowsTokenIdentity("S-1-5-21-9999", False, 8192),
            "unauthorized",
        ),
    ],
)
def test_pipe_server_rejects_ineligible_client_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity: WindowsTokenIdentity,
    message: str,
) -> None:
    core = AuthorityServiceCore(tmp_path / "service")
    server = NamedPipeAuthorityServer(core, "S-1-5-21-1000")
    monkeypatch.setattr(
        "keeper.authority_service.ipc_server.named_pipe_client_identity",
        lambda _pipe: identity,
    )

    with pytest.raises(PermissionError, match=message):
        server._authenticated_client_sid(1)


def test_pipe_server_accepts_authorized_medium_unrestricted_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = AuthorityServiceCore(tmp_path / "service")
    server = NamedPipeAuthorityServer(core, "S-1-5-21-1000")
    monkeypatch.setattr(
        "keeper.authority_service.ipc_server.named_pipe_client_identity",
        lambda _pipe: WindowsTokenIdentity(
            "S-1-5-21-1000", False, 8192
        ),
    )

    assert server._authenticated_client_sid(1) == "S-1-5-21-1000"
