"""AI 服务 API key 的凭据库存取与脱敏。"""
from __future__ import annotations

import ctypes
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from peach import ai_filename_guess_credentials as credentials
from peach import error_reporting


class MemoryBackend:
    def __init__(self):
        self.values: dict[str, str] = {}

    def read(self, target: str) -> str | None:
        return self.values.get(target)

    def write(self, target: str, secret: str) -> None:
        self.values[target] = secret

    def delete(self, target: str) -> bool:
        return self.values.pop(target, None) is not None


class FakeWindowsApi:
    """只实现写与删；读的统一返回「未找到」。

    函数放在实例上而不是定义成方法：ctypes 声明会往属性上写 `argtypes` / `restype`，
    绑定方法没有 `__dict__`，接不住。
    """

    def __init__(self):
        self.saved: tuple[str, str] | None = None
        self.deleted: list[str] = []
        self.write_result = 1

        def CredWriteW(pointer, flags):
            credential = pointer._obj
            raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            self.saved = (credential.TargetName, raw.decode("utf-16-le"))
            return self.write_result

        def CredReadW(target, kind, flags, out):
            return 0

        def CredDeleteW(target, kind, flags):
            self.deleted.append(target)
            return 1

        def CredFree(pointer):
            return None

        self.CredWriteW = CredWriteW
        self.CredReadW = CredReadW
        self.CredDeleteW = CredDeleteW
        self.CredFree = CredFree


class ApiKeyStoreTests(unittest.TestCase):
    def test_save_load_delete_and_survive_a_new_store_instance(self):
        backend = MemoryBackend()
        first = credentials.ApiKeyStore(backend)
        first.save("sk-secret-value")
        self.assertEqual(first.load(), "sk-secret-value")
        second = credentials.ApiKeyStore(backend)
        self.assertEqual(second.load(), "sk-secret-value")
        self.assertTrue(second.delete())
        self.assertFalse(second.delete())
        self.assertIsNone(second.load())

    def test_target_names_are_scoped_per_provider(self):
        backend = MemoryBackend()
        store = credentials.ApiKeyStore(backend)
        store.save("key-a", provider="deepseek")
        store.save("key-b", provider="openai")
        self.assertEqual(store.target("deepseek"), "Peach/AI/FilenameGuess/deepseek")
        self.assertEqual(backend.values, {
            "Peach/AI/FilenameGuess/deepseek": "key-a",
            "Peach/AI/FilenameGuess/openai": "key-b",
        })
        self.assertEqual(store.load(provider="openai"), "key-b")
        self.assertTrue(store.delete(provider="deepseek"))
        self.assertIsNone(store.load(provider="deepseek"))

    def test_describe_only_reports_presence(self):
        backend = MemoryBackend()
        store = credentials.ApiKeyStore(backend)
        self.assertEqual(store.describe(), {"provider": "deepseek", "present": False})
        store.save("secret-value")
        described = store.describe()
        self.assertEqual(described, {"provider": "deepseek", "present": True})
        self.assertNotIn("secret-value", str(described))

    def test_keys_never_touch_a_peach_data_directory(self):
        with tempfile.TemporaryDirectory() as holder:
            data_root = Path(holder) / "peach-data"
            data_root.mkdir()
            store = credentials.ApiKeyStore(MemoryBackend())
            store.save("sk-never-on-disk")
            self.assertEqual(list(data_root.iterdir()), [])
            for path in data_root.rglob("*"):
                if path.is_file():
                    self.assertNotIn("sk-never-on-disk", path.read_text(encoding="utf-8", errors="ignore"))

    def test_bad_provider_and_empty_key_are_rejected_without_echoing_the_key(self):
        store = credentials.ApiKeyStore(MemoryBackend())
        for provider in ("", "DeepSeek", "../deepseek", "a/b"):
            with self.subTest(provider=provider), self.assertRaises(ValueError):
                store.save("sk-secret", provider=provider)
        with self.assertRaises(ValueError) as caught:
            store.save("   ")
        self.assertNotIn("sk-secret", str(caught.exception))

    def test_the_default_store_is_unavailable_off_windows(self):
        if os.name == "nt":
            self.skipTest("Windows has a real credential manager")
        with self.assertRaises(credentials.CredentialStoreUnavailable):
            credentials.ApiKeyStore()
        with self.assertRaises(credentials.CredentialStoreUnavailable):
            credentials.WindowsCredentialManager()

    @unittest.skipUnless(os.name == "nt", "真实凭据管理器只在 Windows 上")
    def test_a_real_windows_credential_survives_a_new_store_instance(self):
        import uuid

        provider = f"test-{uuid.uuid4().hex}"
        first = credentials.ApiKeyStore()
        try:
            first.save("sk-real-secret", provider=provider)
            restarted = credentials.ApiKeyStore()
            self.assertEqual(restarted.load(provider=provider), "sk-real-secret")
            self.assertTrue(restarted.delete(provider=provider))
            self.assertIsNone(restarted.load(provider=provider))
        finally:
            first.delete(provider=provider)


class WindowsBackendTests(unittest.TestCase):
    def test_write_delete_and_not_found_use_the_expected_win32_target(self):
        api = FakeWindowsApi()
        backend = credentials.WindowsCredentialManager(advapi32=api)
        backend.write("Peach/AI/FilenameGuess/deepseek", "sk-secret")
        self.assertEqual(api.saved, ("Peach/AI/FilenameGuess/deepseek", "sk-secret"))
        self.assertTrue(backend.delete("Peach/AI/FilenameGuess/deepseek"))
        self.assertEqual(api.deleted, ["Peach/AI/FilenameGuess/deepseek"])
        with mock.patch.object(credentials, "_last_error",
                               return_value=credentials.ERROR_NOT_FOUND):
            self.assertIsNone(backend.read("Peach/AI/FilenameGuess/deepseek"))

    def test_failed_reads_translate_to_a_fixed_error_without_the_secret(self):
        api = FakeWindowsApi()
        backend = credentials.WindowsCredentialManager(advapi32=api)
        with mock.patch.object(credentials, "_last_error", return_value=5):
            with self.assertRaises(credentials.CredentialStoreUnavailable) as caught:
                backend.read("Peach/AI/FilenameGuess/deepseek")
        self.assertNotIn("sk-secret", str(caught.exception))

    def test_failed_writes_translate_to_a_fixed_error_without_the_secret(self):
        api = FakeWindowsApi()
        api.write_result = 0
        backend = credentials.WindowsCredentialManager(advapi32=api)
        with self.assertRaises(credentials.CredentialStoreUnavailable) as caught:
            backend.write("Peach/AI/FilenameGuess/deepseek", "sk-secret")
        self.assertNotIn("sk-secret", str(caught.exception))


class RedactionTests(unittest.TestCase):
    def test_authorization_is_masked_and_the_scheme_is_kept(self):
        self.assertEqual(credentials.mask_authorization("Bearer sk-secret"), "Bearer <redacted>")
        self.assertEqual(credentials.mask_authorization("sk-secret"), "<redacted>")
        self.assertEqual(credentials.mask_authorization(""), "<redacted>")

    def test_redacted_headers_never_include_secret_values(self):
        headers = {
            "Authorization": "Bearer sk-secret",
            "api-key": "sk-secret",
            "Accept": "application/json",
        }
        redacted = credentials.redacted_headers(headers)
        self.assertEqual(redacted, {
            "Authorization": "Bearer <redacted>",
            "api-key": "<redacted>",
            "Accept": "application/json",
        })
        self.assertNotIn("sk-secret", str(redacted))

    def test_the_shared_error_redactor_also_hides_authorization(self):
        redacted = error_reporting.redact("Authorization: Bearer sk-secret")
        self.assertNotIn("sk-secret", redacted)
        self.assertIn("<redacted>", redacted)
