from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Any

import pytest

from keeper.provider_host import signing


KEY_NAME = "DarkSage.KeeperAuthority.ProviderHost.v1"
ACCESS_SIDS = ("S-1-5-18", "S-1-5-32-544", "S-1-5-80-123")


class FakeCngApi:
    def __init__(
        self,
        *,
        existing: bool,
        open_status: int | None = None,
        security_support: int = 1,
    ) -> None:
        self.existing = existing
        self.open_status = open_status
        self.security_support = security_support
        self.provider_handle = 101
        self.key_handle = 202
        self.provider_name = ""
        self.key_name = KEY_NAME
        self.unique_name = "keeper-machine-key-container"
        self.algorithm = "RSA"
        self.length = 3072
        self.export_policy = 0
        self.security_descriptor: bytes | None = None
        self.create_calls = 0
        self.finalize_calls = 0
        self.security_set_calls = 0
        self.fail_security_set_once = False
        self.fail_security_read = False
        self.free_calls: list[int] = []

    @staticmethod
    def _set_handle(pointer: Any, value: int) -> None:
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p)).contents.value = value

    @staticmethod
    def _set_dword(pointer: Any, value: int) -> None:
        ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD)).contents.value = value

    def NCryptOpenStorageProvider(
        self, output: Any, name: str, _flags: int
    ) -> int:
        self.provider_name = name
        self._set_handle(output, self.provider_handle)
        return 0

    def NCryptOpenKey(
        self,
        _provider: Any,
        output: Any,
        name: str,
        _legacy_spec: int,
        _flags: int,
    ) -> int:
        self.key_name = name if self.key_name == KEY_NAME else self.key_name
        if self.open_status is not None:
            return self.open_status
        if not self.existing:
            return 0x80090016
        self._set_handle(output, self.key_handle)
        return 0

    def NCryptCreatePersistedKey(
        self,
        _provider: Any,
        output: Any,
        algorithm: str,
        name: str,
        _legacy_spec: int,
        _flags: int,
    ) -> int:
        self.create_calls += 1
        self.existing = True
        self.algorithm = algorithm
        self.key_name = name
        self._set_handle(output, self.key_handle)
        return 0

    def NCryptFinalizeKey(self, _key: Any, _flags: int) -> int:
        self.finalize_calls += 1
        return 0

    def NCryptSetProperty(
        self,
        _handle: Any,
        name: str,
        value: Any,
        length: int,
        flags: int,
    ) -> int:
        raw = ctypes.string_at(value, length)
        if name == "Length":
            self.length = int.from_bytes(raw, "little")
            return 0
        if name == "Security Descr":
            self.security_set_calls += 1
            assert flags == (
                signing._OWNER_SECURITY_INFORMATION
                | signing._DACL_SECURITY_INFORMATION
            )
            if self.fail_security_set_once:
                self.fail_security_set_once = False
                return 5
            self.security_descriptor = raw
            return 0
        raise AssertionError(f"unexpected property set: {name}")

    def NCryptGetProperty(
        self,
        handle: Any,
        name: str,
        output: Any | None,
        output_length: int,
        copied: Any,
        flags: int,
    ) -> int:
        handle_value = int(getattr(handle, "value", handle))
        if handle_value == self.provider_handle:
            assert name == "Security Descr Support"
            raw = self.security_support.to_bytes(4, "little")
        else:
            values = {
                "Name": (self.key_name + "\x00").encode("utf-16-le"),
                "Unique Name": (self.unique_name + "\x00").encode("utf-16-le"),
                "Algorithm Name": (self.algorithm + "\x00").encode("utf-16-le"),
                "Length": self.length.to_bytes(4, "little"),
                "Export Policy": self.export_policy.to_bytes(4, "little"),
            }
            if name == "Security Descr":
                assert flags == signing._KEY_SECURITY_INFORMATION
                if self.fail_security_read:
                    return 5
                if self.security_descriptor is None:
                    return 0x80090011
                raw = self.security_descriptor
            else:
                raw = values[name]
        self._set_dword(copied, len(raw))
        if output is not None:
            assert output_length == len(raw)
            ctypes.memmove(output, raw, len(raw))
        return 0

    def NCryptFreeObject(self, handle: Any) -> int:
        self.free_calls.append(int(getattr(handle, "value", handle)))
        return 0


def _open(api: FakeCngApi) -> tuple[ctypes.c_void_p, ctypes.c_void_p]:
    return signing._open_key(
        api,
        KEY_NAME,
        machine_key=True,
        owner_sid=None,
        create_if_missing=True,
        machine_access_sids=ACCESS_SIDS,
    )


def test_security_descriptor_bindings_use_advapi32() -> None:
    advapi32, kernel32 = signing._security_descriptor_apis()
    assert advapi32.GetSecurityDescriptorLength.argtypes == [wintypes.LPVOID]
    assert advapi32.GetSecurityDescriptorLength.restype is wintypes.DWORD
    assert not hasattr(kernel32, "GetSecurityDescriptorLength")
    with signing._key_security_descriptor_for_sddl(
        signing._machine_key_security_sddl(ACCESS_SIDS)
    ) as (descriptor, length):
        assert length > 0
        assert signing._security_descriptor_to_sddl(
            descriptor, signing._KEY_SECURITY_INFORMATION
        ).startswith("O:BAD:P")


def test_missing_security_descriptor_export_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingApi:
        pass

    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: MissingApi())
    with pytest.raises(RuntimeError, match="required Windows"):
        signing._security_descriptor_apis()


def test_no_orphan_creates_one_exact_protected_machine_key() -> None:
    api = FakeCngApi(existing=False)
    provider, key = _open(api)
    assert api.provider_name == signing._SOFTWARE_KEY_STORAGE_PROVIDER
    assert api.create_calls == 1
    assert api.finalize_calls == 1
    assert api.security_set_calls == 1
    assert api.security_descriptor is not None
    api.NCryptFreeObject(key)
    api.NCryptFreeObject(provider)


def test_matching_orphan_is_reconciled_without_recreation() -> None:
    api = FakeCngApi(existing=True)
    provider, key = _open(api)
    assert api.create_calls == 0
    assert api.finalize_calls == 0
    assert api.security_set_calls == 1
    assert api.security_descriptor is not None
    api.NCryptFreeObject(key)
    api.NCryptFreeObject(provider)


@pytest.mark.parametrize(
    ("property_name", "value"),
    [
        ("key_name", "Other.Key"),
        ("unique_name", ""),
        ("algorithm", "ECDSA"),
        ("length", 2048),
        ("export_policy", 1),
    ],
)
def test_existing_machine_key_mismatch_fails_before_acl_change(
    property_name: str, value: object
) -> None:
    api = FakeCngApi(existing=True)
    setattr(api, property_name, value)
    with pytest.raises(PermissionError, match="identity differs"):
        _open(api)
    assert api.create_calls == 0
    assert api.security_set_calls == 0
    assert api.free_calls == [api.key_handle, api.provider_handle]


def test_inaccessible_existing_state_fails_without_creation() -> None:
    api = FakeCngApi(existing=True, open_status=0x80090022)
    with pytest.raises(OSError, match="key open"):
        _open(api)
    assert api.create_calls == 0
    assert api.free_calls == [api.provider_handle]


def test_provider_without_security_descriptor_support_fails_closed() -> None:
    api = FakeCngApi(existing=True, security_support=0)
    with pytest.raises(PermissionError, match="cannot enforce"):
        _open(api)
    assert api.create_calls == 0
    assert api.free_calls == [api.provider_handle]


def test_acl_readback_failure_closes_every_handle() -> None:
    api = FakeCngApi(existing=True)
    api.fail_security_read = True
    with pytest.raises(OSError, match="Security Descr property"):
        _open(api)
    assert api.create_calls == 0
    assert api.security_set_calls == 1
    assert api.free_calls == [api.key_handle, api.provider_handle]


def test_interrupted_new_key_reconciles_on_exact_retry() -> None:
    api = FakeCngApi(existing=False)
    api.fail_security_set_once = True
    with pytest.raises(OSError, match="owner and DACL"):
        _open(api)
    assert api.existing is True
    assert api.create_calls == 1
    assert api.finalize_calls == 1
    assert api.security_descriptor is None
    assert api.free_calls == [api.key_handle, api.provider_handle]

    provider, key = _open(api)
    assert api.create_calls == 1
    assert api.finalize_calls == 1
    assert api.security_set_calls == 2
    assert api.security_descriptor is not None
    api.NCryptFreeObject(key)
    api.NCryptFreeObject(provider)


def test_changed_acl_readback_rejects_adoption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FakeCngApi(existing=True)
    values = iter(["O:BAD:P(A;;GA;;;SY)", "O:BAD:P(A;;GR;;;SY)"])
    monkeypatch.setattr(
        signing, "_security_descriptor_to_sddl", lambda *_: next(values)
    )
    with pytest.raises(PermissionError, match="did not verify exactly"):
        _open(api)
    assert api.free_calls == [api.key_handle, api.provider_handle]
