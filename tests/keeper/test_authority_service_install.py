from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from keeper.authority_service.service_install import AuthorityServiceInstaller


def test_authority_service_package_is_self_contained(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[2]
    package = tmp_path / "keeper-authority.pyz"
    AuthorityServiceInstaller(repository)._build_package(package)

    result = subprocess.run(
        [sys.executable, str(package), "--help"],
        cwd=tmp_path,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=30,
    )

    assert result.returncode == 0
    assert "service" in result.stdout
    assert "console" in result.stdout
