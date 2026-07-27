from __future__ import annotations

import os
from pathlib import Path

import pytest

from keeper.authority_service.restricted_process import (
    restricted_current_process_token,
    run_restricted_process,
)


@pytest.mark.skipif(os.name != "nt", reason="Windows security-token test")
def test_provider_starts_suspended_restricted_low_and_job_confined(
    tmp_path: Path,
) -> None:
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    executable = Path(
        os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "PATHEXT"}
    }
    with restricted_current_process_token() as token:
        result = run_restricted_process(
            token,
            [str(executable), "/d", "/c", "echo restricted-ok"],
            executable,
            tmp_path,
            environment,
            stdout,
            stderr,
            10,
        )

    assert result.exit_code == 0
    assert result.stdout.strip() == "restricted-ok"
    assert result.stderr == ""
    assert result.restricted is True
    assert result.integrity_level == "low"
    assert result.job_confined is True
    assert result.timed_out is False
