from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


_BASE_ALLOWED = {
    "APPDATA",
    "COMPUTERNAME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERDOMAIN",
    "USERNAME",
    "USERPROFILE",
    "WINDIR",
}
_FORBIDDEN_EXACT = {
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "CODEX_ACCESS_TOKEN",
    "CODEX_API_KEY",
    "CODEX_CONFIG",
    "CODEX_HOME",
    "OPENAI_API_KEY",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
}
_FORBIDDEN_FRAGMENTS = (
    "API_KEY",
    "ACCESS_TOKEN",
    "AUTH_TOKEN",
    "BEARER_TOKEN",
    "CLIENT_SECRET",
    "COOKIE",
    "PASSWORD",
    "PAID_FALLBACK",
    "PROXY",
    "REFRESH_TOKEN",
)


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    values: dict[str, str]
    allowlist: tuple[str, ...]
    scrubbed_names: tuple[str, ...]
    digest: str
    preparation_nonce: str

    def public_attestation(self) -> dict[str, object]:
        return {
            "allowlist": list(self.allowlist),
            "digest": self.digest,
            "preparation_nonce": self.preparation_nonce,
            "scrubbed_names": list(self.scrubbed_names),
        }


def build_sanitized_environment(
    source: Mapping[str, str],
    *,
    profile_path: Path,
    provider_bin: Path,
    preparation_nonce: str,
    attestation_key: bytes,
) -> EnvironmentSnapshot:
    profile = profile_path.resolve(strict=True)
    provider = provider_bin.resolve(strict=True)
    if not preparation_nonce or "\x00" in preparation_nonce or not attestation_key:
        raise ValueError("Provider Host environment attestation inputs are required")
    folded: dict[str, tuple[str, str]] = {}
    for raw_name, raw_value in source.items():
        if not isinstance(raw_name, str) or not isinstance(raw_value, str):
            raise PermissionError("Provider Host environment entries must be strings")
        if "\x00" in raw_name or "=" in raw_name or "\x00" in raw_value:
            raise PermissionError("Provider Host environment entry shape is invalid")
        upper = raw_name.upper()
        if upper in folded and folded[upper][0] != raw_name:
            raise PermissionError("Provider Host environment has case aliases")
        folded[upper] = (raw_name, raw_value)
    scrubbed = sorted(
        name
        for name in folded
        if name in _FORBIDDEN_EXACT
        or any(fragment in name for fragment in _FORBIDDEN_FRAGMENTS)
        or name.startswith("HTTP_")
        or name.startswith("HTTPS_")
        or name in {"ALL_PROXY", "NO_PROXY"}
    )
    values: dict[str, str] = {}
    for name in sorted(_BASE_ALLOWED):
        item = folded.get(name)
        if item is not None:
            values[name] = item[1]
    system_root = Path(os.environ["SYSTEMROOT"]).resolve(strict=True)
    values["PATH"] = os.pathsep.join((str(provider), str(system_root / "System32")))
    values["USERPROFILE"] = str(profile)
    _validate_profile_paths(values, profile, system_root)
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    digest = hmac.new(
        attestation_key,
        preparation_nonce.encode("utf-8") + b"\0" + canonical,
        hashlib.sha256,
    ).hexdigest()
    return EnvironmentSnapshot(
        values=values,
        allowlist=tuple(sorted(values, key=str.upper)),
        scrubbed_names=tuple(scrubbed),
        digest=digest,
        preparation_nonce=preparation_nonce,
    )


def assert_attestation_matches(
    snapshot: EnvironmentSnapshot, declared: Mapping[str, object]
) -> None:
    if declared != snapshot.public_attestation():
        raise PermissionError("Provider Host environment attestation differs")


def _validate_profile_paths(
    values: Mapping[str, str], profile: Path, system_root: Path
) -> None:
    for name in ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):
        raw = values.get(name)
        if raw is None:
            continue
        candidate = Path(raw).resolve(strict=True)
        if candidate != profile and profile not in candidate.parents:
            raise PermissionError(f"Provider Host {name} escapes the profile")
    for name in ("SYSTEMROOT", "WINDIR"):
        raw = values.get(name)
        if raw is not None and Path(raw).resolve(strict=True) != system_root:
            raise PermissionError(f"Provider Host {name} differs from Windows")
