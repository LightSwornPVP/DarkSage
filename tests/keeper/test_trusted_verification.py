from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from keeper.app.verification_policy import VerificationSpec, validate_semantic_bindings
from keeper.verifier import VerificationCommand, Verifier


def _trusted_pytest(workspace: Path) -> tuple[bool, dict[str, object] | None]:
    spec = VerificationSpec(
        "tests",
        ["{python}", "-m", "pytest", "-q", "test_real.py"],
        "pytest",
        registration_id="pytest:trusted-environment",
    )
    validate_semantic_bindings([spec], ["tests"])
    result = Verifier().run(
        workspace,
        [
            VerificationCommand(
                spec.arguments,
                validator=spec.validator,
                registration_id=spec.registration_id,
            )
        ],
    )[0]
    return result.passed, result.validator_identity


@pytest.mark.parametrize("shadow_kind", ["module", "package"])
def test_workspace_pytest_shadowing_is_ignored(
    tmp_path: Path, shadow_kind: str
) -> None:
    if shadow_kind == "module":
        (tmp_path / "pytest.py").write_text(
            "raise SystemExit('workspace pytest executed')\n", encoding="utf-8"
        )
    else:
        package = tmp_path / "pytest"
        package.mkdir()
        (package / "__main__.py").write_text(
            "raise SystemExit('workspace pytest package executed')\n", encoding="utf-8"
        )
    (tmp_path / "test_real.py").write_text(
        "def test_real():\n    assert True\n", encoding="utf-8"
    )
    passed, identity = _trusted_pytest(tmp_path)
    assert passed
    assert identity is not None
    assert not Path(str(identity["module_origin"])).is_relative_to(tmp_path)


def test_import_environment_is_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    malicious = tmp_path / "malicious"
    malicious.mkdir()
    (malicious / "pytest.py").write_text(
        "raise SystemExit('PYTHONPATH shadow executed')\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(malicious))
    monkeypatch.setenv("PYTHONHOME", str(malicious))
    monkeypatch.setenv("PYTHONUSERBASE", str(malicious))
    (tmp_path / "test_real.py").write_text(
        "def test_real():\n    assert True\n", encoding="utf-8"
    )
    assert _trusted_pytest(tmp_path)[0]


def test_executable_substitution_is_rejected() -> None:
    with pytest.raises(ValueError, match="Python pytest module"):
        validate_semantic_bindings(
            [
                VerificationSpec(
                    "tests",
                    [os.fspath(Path("fake-python.exe")), "-m", "pytest"],
                    "pytest",
                )
            ],
            ["tests"],
        )


def test_zero_exit_fake_stdout_cannot_satisfy_pytest(tmp_path: Path) -> None:
    fake = tmp_path / "fake.cmd"
    fake.write_text("@echo fabricated success\r\n@exit /b 0\r\n", encoding="ascii")
    with pytest.raises(ValueError):
        validate_semantic_bindings(
            [VerificationSpec("tests", [str(fake), "-m", "pytest"], "pytest")],
            ["tests"],
        )


def test_foundation_script_is_pinned_and_must_not_be_symlink(
    tmp_path: Path,
) -> None:
    script = tmp_path / "scripts" / "verify-foundation.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    spec = VerificationSpec(
        "foundation",
        [str(script)],
        "foundation-script",
        expected_sha256=digest,
    )
    validate_semantic_bindings([spec], ["foundation"])
    script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    with pytest.raises(PermissionError, match="hash"):
        validate_semantic_bindings([spec], ["foundation"])
    link = tmp_path / "linked" / "scripts" / "verify-foundation.sh"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(script)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    linked = VerificationSpec(
        "foundation",
        [str(link)],
        "foundation-script",
        expected_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="regular file"):
        validate_semantic_bindings([linked], ["foundation"])


def test_genuine_trusted_validator_records_identity(tmp_path: Path) -> None:
    (tmp_path / "test_real.py").write_text(
        "def test_real():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )
    passed, identity = _trusted_pytest(tmp_path)
    assert passed
    assert identity is not None
    assert identity["registration_id"] == "pytest:trusted-environment"
    assert identity["environment_policy"] == "isolated-no-user-site-no-pythonpath"
