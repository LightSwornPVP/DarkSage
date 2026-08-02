from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import os
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Iterator, Mapping

from keeper.provider_host.protocol import (
    CallbackEnvelopeIdentity,
    canonical_json,
)


_RSA_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")
_NCRYPT_MACHINE_KEY_FLAG = 0x00000020
_NCRYPT_SILENT_FLAG = 0x00000040
_NCRYPT_PAD_PKCS1_FLAG = 0x00000002
_DACL_SECURITY_INFORMATION = 0x00000004
_SDDL_REVISION_1 = 1
_RESTRICTED_CODE_SID = "S-1-5-12"


class _BcryptRsaKeyBlob(ctypes.Structure):
    _fields_ = [
        ("Magic", wintypes.ULONG),
        ("BitLength", wintypes.ULONG),
        ("cbPublicExp", wintypes.ULONG),
        ("cbModulus", wintypes.ULONG),
        ("cbPrime1", wintypes.ULONG),
        ("cbPrime2", wintypes.ULONG),
    ]


class _BcryptPkcs1PaddingInfo(ctypes.Structure):
    _fields_ = [("pszAlgId", wintypes.LPCWSTR)]


@dataclass(frozen=True, slots=True)
class RsaPublicIdentity:
    identity: str
    key_id: str
    modulus: bytes
    exponent: bytes
    production: bool = True

    @classmethod
    def from_configuration(cls, value: Mapping[str, object]) -> RsaPublicIdentity:
        expected = {"algorithm", "exponent", "identity", "key_id", "modulus", "schema_version"}
        if (
            set(value) != expected
            or value.get("schema_version") != 1
            or value.get("algorithm") != "RSA-PKCS1-SHA256"
        ):
            raise PermissionError("Provider Host public identity is invalid")
        try:
            modulus = base64.b64decode(str(value["modulus"]), validate=True)
            exponent = base64.b64decode(str(value["exponent"]), validate=True)
        except ValueError as error:
            raise PermissionError("Provider Host public key is invalid") from error
        identity = str(value["identity"])
        key_id = str(value["key_id"])
        public = {"algorithm": "RSA-PKCS1-SHA256", "exponent": value["exponent"], "modulus": value["modulus"]}
        expected_key_id = "keeper-provider-host-rsa:" + hashlib.sha256(
            canonical_json(public)
        ).hexdigest()
        if (
            not identity
            or key_id != expected_key_id
            or int.from_bytes(modulus, "big").bit_length() < 2048
            or int.from_bytes(exponent, "big") < 3
            or int.from_bytes(exponent, "big") % 2 == 0
        ):
            raise PermissionError("Provider Host public key binding is invalid")
        return cls(identity, key_id, modulus, exponent)

    def verify_digest(self, digest: bytes, signature: bytes) -> bool:
        return _rsa_verify(self.modulus, self.exponent, digest, signature)

    def verifier(self) -> CallbackEnvelopeIdentity:
        def no_sign(_: bytes) -> bytes:
            raise PermissionError("Provider Host public identity cannot sign")

        return CallbackEnvelopeIdentity(
            self.identity,
            self.key_id,
            no_sign,
            self.verify_digest,
            True,
        )


class WindowsCngEnvelopeIdentity:
    """Non-exportable Windows CNG RSA identity for Authority or user host."""

    def __init__(
        self,
        *,
        identity: str,
        key_name: str,
        machine_key: bool,
        owner_sid: str | None = None,
        create_if_missing: bool = True,
        machine_access_sids: tuple[str, ...] = (),
    ) -> None:
        if os.name != "nt" or not identity or not key_name:
            raise RuntimeError("Provider Host CNG identity requires Windows")
        if machine_key and owner_sid is not None:
            raise ValueError("machine CNG identity cannot use a user owner SID")
        if not machine_key and (
            owner_sid is None or not owner_sid.startswith("S-1-")
        ):
            raise ValueError("user CNG identity requires an exact owner SID")
        if not machine_key and machine_access_sids:
            raise ValueError("user CNG identity cannot use machine access SIDs")
        if machine_key and any(
            not sid.startswith("S-1-") for sid in machine_access_sids
        ):
            raise ValueError("machine CNG identity access SID is invalid")
        if len(set(machine_access_sids)) != len(machine_access_sids):
            raise ValueError("machine CNG identity access SIDs are duplicated")
        self.identity = identity
        self.key_name = key_name
        self.machine_key = machine_key
        self.owner_sid = owner_sid
        self.create_if_missing = create_if_missing
        self.machine_access_sids = machine_access_sids
        modulus, exponent = _public_key(
            key_name,
            machine_key=machine_key,
            owner_sid=owner_sid,
            create_if_missing=create_if_missing,
            machine_access_sids=machine_access_sids,
        )
        self._public = RsaPublicIdentity.from_configuration(
            _public_configuration(identity, modulus, exponent)
        )
        self.key_id = self._public.key_id
        self.production = True

    def sign(self, purpose: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        codec = CallbackEnvelopeIdentity(
            self.identity,
            self.key_id,
            lambda digest: _sign(
                self.key_name,
                digest,
                machine_key=self.machine_key,
                owner_sid=self.owner_sid,
                create_if_missing=self.create_if_missing,
                machine_access_sids=self.machine_access_sids,
            ),
            self._public.verify_digest,
            True,
        )
        return codec.sign(purpose, payload)

    def verify(
        self, record: Mapping[str, Any], *, purpose: str
    ) -> dict[str, Any]:
        return self._public.verifier().verify(record, purpose=purpose)

    def public_configuration(self) -> dict[str, object]:
        return _public_configuration(
            self.identity, self._public.modulus, self._public.exponent
        )


def _public_configuration(
    identity: str, modulus: bytes, exponent: bytes
) -> dict[str, object]:
    public = {
        "algorithm": "RSA-PKCS1-SHA256",
        "exponent": base64.b64encode(exponent).decode("ascii"),
        "modulus": base64.b64encode(modulus).decode("ascii"),
    }
    return {
        "schema_version": 1,
        "identity": identity,
        "key_id": "keeper-provider-host-rsa:"
        + hashlib.sha256(canonical_json(public)).hexdigest(),
        **public,
    }


def _rsa_verify(
    modulus_bytes: bytes,
    exponent_bytes: bytes,
    digest: bytes,
    signature: bytes,
) -> bool:
    modulus = int.from_bytes(modulus_bytes, "big")
    exponent = int.from_bytes(exponent_bytes, "big")
    if (
        len(digest) != 32
        or modulus.bit_length() < 2048
        or exponent < 3
        or exponent % 2 == 0
        or len(signature) != len(modulus_bytes)
    ):
        return False
    encoded = pow(int.from_bytes(signature, "big"), exponent, modulus).to_bytes(
        len(modulus_bytes), "big"
    )
    digest_info = _RSA_SHA256_DIGEST_INFO + digest
    padding_length = len(encoded) - len(digest_info) - 3
    expected = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    return padding_length >= 8 and hmac.compare_digest(encoded, expected)


def _public_key(
    name: str,
    *,
    machine_key: bool,
    owner_sid: str | None,
    create_if_missing: bool,
    machine_access_sids: tuple[str, ...],
) -> tuple[bytes, bytes]:
    api = _ncrypt()
    provider, key = _open_key(
        api,
        name,
        machine_key=machine_key,
        owner_sid=owner_sid,
        create_if_missing=create_if_missing,
        machine_access_sids=machine_access_sids,
    )
    try:
        required = wintypes.DWORD()
        _check(
            api.NCryptExportKey(
                key,
                None,
                "RSAPUBLICBLOB",
                None,
                None,
                0,
                ctypes.byref(required),
                0,
            ),
            "public-key size",
        )
        buffer = ctypes.create_string_buffer(required.value)
        _check(
            api.NCryptExportKey(
                key,
                None,
                "RSAPUBLICBLOB",
                None,
                buffer,
                required.value,
                ctypes.byref(required),
                0,
            ),
            "public-key export",
        )
        header = _BcryptRsaKeyBlob.from_buffer_copy(buffer.raw)
        if header.Magic != 0x31415352 or header.BitLength < 2048:
            raise RuntimeError("Provider Host CNG public key is invalid")
        offset = ctypes.sizeof(_BcryptRsaKeyBlob)
        exponent = buffer.raw[offset : offset + header.cbPublicExp]
        offset += header.cbPublicExp
        modulus = buffer.raw[offset : offset + header.cbModulus]
        return modulus, exponent
    finally:
        api.NCryptFreeObject(key)
        api.NCryptFreeObject(provider)


def _sign(
    name: str,
    digest: bytes,
    *,
    machine_key: bool,
    owner_sid: str | None,
    create_if_missing: bool,
    machine_access_sids: tuple[str, ...],
) -> bytes:
    if len(digest) != 32:
        raise ValueError("Provider Host signing digest is invalid")
    api = _ncrypt()
    provider, key = _open_key(
        api,
        name,
        machine_key=machine_key,
        owner_sid=owner_sid,
        create_if_missing=create_if_missing,
        machine_access_sids=machine_access_sids,
    )
    padding = _BcryptPkcs1PaddingInfo("SHA256")
    digest_buffer = ctypes.create_string_buffer(digest)
    try:
        required = wintypes.DWORD()
        _check(
            api.NCryptSignHash(
                key,
                ctypes.byref(padding),
                digest_buffer,
                len(digest),
                None,
                0,
                ctypes.byref(required),
                _NCRYPT_PAD_PKCS1_FLAG,
            ),
            "signature size",
        )
        signature = ctypes.create_string_buffer(required.value)
        _check(
            api.NCryptSignHash(
                key,
                ctypes.byref(padding),
                digest_buffer,
                len(digest),
                signature,
                required.value,
                ctypes.byref(required),
                _NCRYPT_PAD_PKCS1_FLAG,
            ),
            "signature",
        )
        return signature.raw[: required.value]
    finally:
        api.NCryptFreeObject(key)
        api.NCryptFreeObject(provider)


def _open_key(
    api: Any,
    name: str,
    *,
    machine_key: bool,
    owner_sid: str | None,
    create_if_missing: bool = True,
    machine_access_sids: tuple[str, ...] = (),
) -> tuple[ctypes.c_void_p, ctypes.c_void_p]:
    provider = ctypes.c_void_p()
    key = ctypes.c_void_p()
    _check(
        api.NCryptOpenStorageProvider(
            ctypes.byref(provider),
            "Microsoft Software Key Storage Provider",
            0,
        ),
        "provider open",
    )
    flags = _NCRYPT_SILENT_FLAG | (
        _NCRYPT_MACHINE_KEY_FLAG if machine_key else 0
    )
    status = api.NCryptOpenKey(provider, ctypes.byref(key), name, 0, flags)
    if status == 0:
        if owner_sid is not None:
            _protect_user_key(api, key, owner_sid)
        elif machine_access_sids:
            _protect_machine_key(api, key, machine_access_sids)
        return provider, key
    if status & 0xFFFFFFFF not in {0x80090016, 0x8009000D}:
        api.NCryptFreeObject(provider)
        _check(status, "key open")
    if not create_if_missing:
        api.NCryptFreeObject(provider)
        raise PermissionError("Provider Host CNG key is not provisioned")
    if machine_key and not machine_access_sids:
        api.NCryptFreeObject(provider)
        raise PermissionError(
            "machine Provider Host CNG key requires an explicit access policy"
        )
    try:
        _check(
            api.NCryptCreatePersistedKey(
                provider,
                ctypes.byref(key),
                "RSA",
                name,
                0,
                flags,
            ),
            "key creation",
        )
        length = wintypes.DWORD(3072)
        _check(
            api.NCryptSetProperty(
                key,
                "Length",
                ctypes.byref(length),
                ctypes.sizeof(length),
                0,
            ),
            "key length",
        )
        _check(api.NCryptFinalizeKey(key, _NCRYPT_SILENT_FLAG), "key finalization")
        if owner_sid is not None:
            _protect_user_key(api, key, owner_sid)
        elif machine_access_sids:
            _protect_machine_key(api, key, machine_access_sids)
        return provider, key
    except BaseException:
        if key:
            api.NCryptFreeObject(key)
        api.NCryptFreeObject(provider)
        raise


def _protect_user_key(api: Any, key: ctypes.c_void_p, owner_sid: str) -> None:
    """Persist an exact DACL that excludes every restricted provider token."""
    with _key_security_descriptor(owner_sid) as (descriptor, length):
        _check(
            api.NCryptSetProperty(
                key,
                "Security Descr",
                descriptor,
                length,
                _DACL_SECURITY_INFORMATION,
            ),
            "restricted-provider DACL",
        )


def _protect_machine_key(
    api: Any, key: ctypes.c_void_p, access_sids: tuple[str, ...]
) -> None:
    """Persist an exact machine-key DACL supplied by elevated lifecycle code."""
    with _key_security_descriptor_for_sddl(
        _machine_key_security_sddl(access_sids)
    ) as (descriptor, length):
        _check(
            api.NCryptSetProperty(
                key,
                "Security Descr",
                descriptor,
                length,
                _DACL_SECURITY_INFORMATION,
            ),
            "machine-key DACL",
        )


@contextmanager
def _key_security_descriptor(
    owner_sid: str,
) -> Iterator[tuple[wintypes.LPVOID, int]]:
    if not owner_sid.startswith("S-1-"):
        raise ValueError("Provider Host key owner SID is invalid")
    with _key_security_descriptor_for_sddl(
        _key_security_sddl(owner_sid)
    ) as value:
        yield value


@contextmanager
def _key_security_descriptor_for_sddl(
    sddl: str,
) -> Iterator[tuple[wintypes.LPVOID, int]]:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
        wintypes.BOOL
    )
    kernel32.GetSecurityDescriptorLength.argtypes = [wintypes.LPVOID]
    kernel32.GetSecurityDescriptorLength.restype = wintypes.DWORD
    kernel32.LocalFree.restype = wintypes.HLOCAL
    descriptor = wintypes.LPVOID()
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl,
        _SDDL_REVISION_1,
        ctypes.byref(descriptor),
        None,
    ):
        raise OSError(
            ctypes.get_last_error(),
            "Provider Host key DACL creation failed",
        )
    try:
        length = int(kernel32.GetSecurityDescriptorLength(descriptor))
        if length <= 0:
            raise OSError("Provider Host key DACL length is invalid")
        yield descriptor, length
    finally:
        kernel32.LocalFree(descriptor)


def _key_security_sddl(owner_sid: str) -> str:
    if not owner_sid.startswith("S-1-"):
        raise ValueError("Provider Host key owner SID is invalid")
    return (
        f"D:P(D;;GA;;;{_RESTRICTED_CODE_SID})"
        f"(A;;GA;;;SY)(A;;GA;;;{owner_sid})"
    )


def _machine_key_security_sddl(access_sids: tuple[str, ...]) -> str:
    if (
        not access_sids
        or any(not sid.startswith("S-1-") for sid in access_sids)
        or len(set(access_sids)) != len(access_sids)
    ):
        raise ValueError("Provider Host machine-key access policy is invalid")
    grants = "".join(f"(A;;GA;;;{sid})" for sid in access_sids)
    return f"D:P(D;;GA;;;{_RESTRICTED_CODE_SID}){grants}"


def _check(status: int, operation: str) -> None:
    if status != 0:
        raise OSError(status & 0xFFFFFFFF, f"Provider Host CNG {operation} failed")


def _ncrypt() -> Any:
    if os.name != "nt":
        raise RuntimeError("Provider Host CNG requires Windows")
    api: Any = ctypes.WinDLL("ncrypt.dll")
    handle = ctypes.c_void_p
    dword = wintypes.DWORD
    pointer = ctypes.c_void_p
    api.NCryptOpenStorageProvider.argtypes = [ctypes.POINTER(handle), wintypes.LPCWSTR, dword]
    api.NCryptOpenKey.argtypes = [handle, ctypes.POINTER(handle), wintypes.LPCWSTR, dword, dword]
    api.NCryptCreatePersistedKey.argtypes = [handle, ctypes.POINTER(handle), wintypes.LPCWSTR, wintypes.LPCWSTR, dword, dword]
    api.NCryptSetProperty.argtypes = [handle, wintypes.LPCWSTR, pointer, dword, dword]
    api.NCryptFinalizeKey.argtypes = [handle, dword]
    api.NCryptExportKey.argtypes = [handle, handle, wintypes.LPCWSTR, pointer, pointer, dword, ctypes.POINTER(dword), dword]
    api.NCryptSignHash.argtypes = [handle, pointer, pointer, dword, pointer, dword, ctypes.POINTER(dword), dword]
    api.NCryptFreeObject.argtypes = [handle]
    for function in (
        api.NCryptOpenStorageProvider,
        api.NCryptOpenKey,
        api.NCryptCreatePersistedKey,
        api.NCryptSetProperty,
        api.NCryptFinalizeKey,
        api.NCryptExportKey,
        api.NCryptSignHash,
        api.NCryptFreeObject,
    ):
        function.restype = ctypes.c_long
    return api
