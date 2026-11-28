"""AI 服务的 API key 存取。

key 只进操作系统凭据库：Windows 用凭据管理器（通用凭据），不落 `peach-data`、不进 Git、
日志、错误原文或诊断包。读不到 key 是正常状态，返回 `None`；凭据库不可用才报错，错误
文字固定，不含 key 本身。

非 Windows 平台默认没有可用的后端，`ApiKeyStore()` 会明确报不可用；调用方可以在测试或
其他宿主里注入实现同一读写协议的后端。授权头脱敏用 `redacted_headers`，供后续 API
客户端记录请求时使用。
"""
from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes
from typing import Protocol

from .user_messages import UserRuntimeError

#: 功能默认服务商；模型与提示词版本在 `ai_filename_guess`。
DEFAULT_PROVIDER = "deepseek"
#: 凭据管理器里的目标名前缀，按服务商区分；不写进任何数据文件。
TARGET_PREFIX = "Peach/AI/FilenameGuess/"
#: Win32 `CRED_TYPE_GENERIC` 与 `CRED_PERSIST_LOCAL_MACHINE`。
CREDENTIAL_TYPE_GENERIC = 1
CREDENTIAL_PERSIST_LOCAL_MACHINE = 2
#: `CredReadW` / `CredDeleteW` 找不到目标时返回的 Win32 错误码。
ERROR_NOT_FOUND = 1168

_PROVIDER = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_SECRET_HEADERS = frozenset({"authorization", "proxy-authorization", "api-key", "x-api-key"})


def _last_error() -> int:
    """`ctypes.get_last_error` 只在 Windows 上存在；注入后端与测试在没有它时按 0 处理。"""
    getter = getattr(ctypes, "get_last_error", None)
    return getter() if getter is not None else 0


class CredentialStoreUnavailable(UserRuntimeError):
    """系统凭据库不可用；错误文字固定，绝不带 key。"""

    status_code = 500

    def __init__(self) -> None:
        super().__init__("errors.aiFilenameGuess.credentialStoreUnavailable")


class CredentialBackend(Protocol):
    def read(self, target: str) -> str | None: ...

    def write(self, target: str, secret: str) -> None: ...

    def delete(self, target: str) -> bool: ...


class _FileTime(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FileTime),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentialManager:
    """Windows 凭据管理器后端；只在 Windows 上实例化，测试可注入 `advapi32` 替身。"""

    def __init__(self, advapi32=None) -> None:
        if advapi32 is None:
            if os.name != "nt":
                raise CredentialStoreUnavailable()
            advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self._api = advapi32
        self._declare()

    def _declare(self) -> None:
        api = self._api
        api.CredReadW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_CredentialW)),
        ]
        api.CredReadW.restype = wintypes.BOOL
        api.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None

    def read(self, target: str) -> str | None:
        pointer = ctypes.POINTER(_CredentialW)()
        if not self._api.CredReadW(target, CREDENTIAL_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            if _last_error() == ERROR_NOT_FOUND:
                return None
            raise CredentialStoreUnavailable()
        try:
            credential = pointer.contents
            raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return raw.decode("utf-16-le")
        finally:
            self._api.CredFree(pointer)

    def write(self, target: str, secret: str) -> None:
        raw = secret.encode("utf-16-le")
        buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        credential = _CredentialW(
            Flags=0,
            Type=CREDENTIAL_TYPE_GENERIC,
            TargetName=target,
            Comment=None,
            LastWritten=_FileTime(),
            CredentialBlobSize=len(raw),
            CredentialBlob=ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
            Persist=CREDENTIAL_PERSIST_LOCAL_MACHINE,
            AttributeCount=0,
            Attributes=None,
            TargetAlias=None,
            UserName="Peach",
        )
        if not self._api.CredWriteW(ctypes.byref(credential), 0):
            raise CredentialStoreUnavailable()

    def delete(self, target: str) -> bool:
        if self._api.CredDeleteW(target, CREDENTIAL_TYPE_GENERIC, 0):
            return True
        if _last_error() == ERROR_NOT_FOUND:
            return False
        raise CredentialStoreUnavailable()


class ApiKeyStore:
    """按服务商读写 API key；key 不经过 `peach-data`。"""

    def __init__(self, backend: CredentialBackend | None = None, *,
                 target_prefix: str = TARGET_PREFIX) -> None:
        self.backend = backend if backend is not None else WindowsCredentialManager()
        self.target_prefix = target_prefix

    def target(self, provider: str = DEFAULT_PROVIDER) -> str:
        name = str(provider or "").strip()
        if not _PROVIDER.fullmatch(name):
            raise ValueError("provider may only contain lowercase letters, digits, dots, underscores, and hyphens")
        return f"{self.target_prefix}{name}"

    def save(self, key: str, *, provider: str = DEFAULT_PROVIDER) -> None:
        secret = str(key or "").strip()
        if not secret:
            raise ValueError("API key must not be empty")
        self.backend.write(self.target(provider), secret)

    def load(self, *, provider: str = DEFAULT_PROVIDER) -> str | None:
        return self.backend.read(self.target(provider))

    def delete(self, *, provider: str = DEFAULT_PROVIDER) -> bool:
        return self.backend.delete(self.target(provider))

    def describe(self, *, provider: str = DEFAULT_PROVIDER) -> dict[str, object]:
        """只报告是否存在，绝不返回值。"""
        return {"provider": provider, "present": self.load(provider=provider) is not None}


def mask_authorization(value: str) -> str:
    """把 `Authorization` 的凭证部分换成固定标记，保留认证方案。"""
    scheme, separator, _ = str(value or "").partition(" ")
    return f"{scheme} <redacted>" if separator and scheme else "<redacted>"


def redacted_headers(headers: dict[str, str]) -> dict[str, str]:
    """日志或诊断用的请求头副本：Authorization 与 API key 类头部一律打码。"""
    return {
        name: mask_authorization(value) if name.lower() == "authorization" else "<redacted>"
        if name.lower() in _SECRET_HEADERS else value
        for name, value in headers.items()
    }
