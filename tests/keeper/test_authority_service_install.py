from __future__ import annotations

import os
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


def test_authority_service_package_is_reproducible_across_source_mtimes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    keeper = source / "keeper"
    keeper.mkdir(parents=True)
    module = keeper / "__init__.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    first = tmp_path / "first.pyz"
    second = tmp_path / "second.pyz"
    installer = AuthorityServiceInstaller(source)

    os.utime(module, (1_700_000_000, 1_700_000_000))
    installer._build_package(first)
    os.utime(module, (1_800_000_000, 1_800_000_000))
    installer._build_package(second)

    assert first.read_bytes() == second.read_bytes()
