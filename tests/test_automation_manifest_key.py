from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from chrome_extension_python.package_storage import PackageStorage, get_cache_file_path

from nopecha_extension import Nopecha


AUTOMATION_MANIFEST = {
    "nopecha": {
        "key": "",
        "keys": [],
        "enabled": True,
        "hcaptcha_auto_solve": True,
    },
    "name": "NopeCHA: CAPTCHA Solver",
    "permissions": ["scripting", "storage"],
    "manifest_version": 3,
    "host_permissions": ["<all_urls>"],
    "key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKC-extension-public-key",
}

JS_SOURCE = "const label = 'O\\'Brien\\\\1';\napiKey: ''\nNOPECHA_API_KEY\n"
HTML_SOURCE = '<input id="apiKey" value="">\nNOPECHA_API_KEY\n'
SPECIAL_KEY = "O'Brien\\1"


class AutomationManifestKeyTest(unittest.TestCase):
    def _make_extension(self, root: Path, manifest: dict | None = None) -> Path:
        manifest_path = root / "manifest.json"
        payload = AUTOMATION_MANIFEST if manifest is None else manifest
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        (root / "popup.js").write_text(JS_SOURCE, encoding="utf-8")
        (root / "popup.html").write_text(HTML_SOURCE, encoding="utf-8")
        return manifest_path

    def _assert_other_settings_preserved(self, written: dict, api_key: str) -> None:
        self.assertEqual(written["nopecha"]["key"], api_key)
        self.assertEqual(written["nopecha"]["hcaptcha_auto_solve"], True)
        self.assertEqual(written["nopecha"]["keys"], [])
        self.assertEqual(written["nopecha"]["enabled"], True)
        self.assertEqual(written["key"], AUTOMATION_MANIFEST["key"])
        self.assertEqual(written["permissions"], AUTOMATION_MANIFEST["permissions"])
        self.assertEqual(written["host_permissions"], AUTOMATION_MANIFEST["host_permissions"])

    def _assert_scripts_untouched(self, root: Path) -> None:
        self.assertEqual((root / "popup.js").read_text(encoding="utf-8"), JS_SOURCE)
        self.assertEqual((root / "popup.html").read_text(encoding="utf-8"), HTML_SOURCE)

    def test_automation_build_writes_api_key_into_nopecha_settings(self):
        api_key = "sub_test_key_9f3a"
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = self._make_extension(extension_dir)

            ext = Nopecha(api_key=api_key)
            self.assertEqual(ext.kwargs, {})
            ext.extension_path = str(extension_dir)
            report = ext.update_files()

            written = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._assert_scripts_untouched(extension_dir)

        self.assertEqual(report["modified"], ["manifest.json"])
        self.assertEqual(report["skipped"], [])
        self.assertEqual(report["errors"], [])
        self._assert_other_settings_preserved(written, api_key)

    def test_special_characters_in_key_stay_inside_nopecha_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = self._make_extension(extension_dir)
            ext = Nopecha(api_key=SPECIAL_KEY, extension_path=extension_dir)
            report = ext.update_files()
            written = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._assert_scripts_untouched(extension_dir)

        self.assertEqual(report["modified"], ["manifest.json"])
        self._assert_other_settings_preserved(written, SPECIAL_KEY)
        self.assertEqual(written["nopecha"]["key"], "O'Brien\\1")

    def test_update_files_is_idempotent_when_key_already_matches(self):
        api_key = "already-set"
        manifest = json.loads(json.dumps(AUTOMATION_MANIFEST))
        manifest["nopecha"]["key"] = api_key
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = self._make_extension(extension_dir, manifest)
            original = manifest_path.read_bytes()
            modified_at = manifest_path.stat().st_mtime_ns

            ext = Nopecha(api_key=api_key, extension_path=Path(extension_dir))
            first = ext.update_files()
            second = ext.update_files(api_key=api_key)

            self.assertEqual(manifest_path.read_bytes(), original)
            self.assertEqual(manifest_path.stat().st_mtime_ns, modified_at)
            self._assert_scripts_untouched(extension_dir)

        self.assertEqual(first["modified"], [])
        self.assertEqual(first["skipped"], ["manifest.json"])
        self.assertEqual(second["skipped"], ["manifest.json"])
        self.assertEqual(second["modified"], [])

    def test_rejected_api_keys_raise_before_any_write(self):
        rejected = ["", "   ", "\n\t", None, 123, b"sub_test_key"]
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = self._make_extension(extension_dir)
            original = manifest_path.read_bytes()
            for api_key in rejected:
                with self.subTest(api_key=api_key):
                    with self.assertRaises(ValueError):
                        Nopecha(api_key=api_key, extension_path=extension_dir)
                    self.assertEqual(manifest_path.read_bytes(), original)

            ext = Nopecha(api_key="valid-key", extension_path=extension_dir)
            for api_key in ["", "   ", "\n\t", 123, b"sub_test_key"]:
                with self.subTest(patch_api_key=api_key):
                    with self.assertRaises(ValueError):
                        ext.update_files(api_key=api_key)
                    with self.assertRaises(ValueError):
                        ext.quick_patch_file("manifest.json", api_key=api_key)
                    self.assertEqual(manifest_path.read_bytes(), original)

    def test_spaced_key_is_stored_without_stripping(self):
        api_key = "  sub_test_key  "
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = self._make_extension(extension_dir)
            Nopecha(api_key=api_key, extension_path=extension_dir).update_files()
            written = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(written["nopecha"]["key"], api_key)

    def test_update_files_enables_all_captcha_types(self):
        api_key = "already-set"
        manifest = json.loads(json.dumps(AUTOMATION_MANIFEST))
        manifest["nopecha"] = {
            "key": api_key,
            "keys": [],
            "enabled": False,
            "disabled_hosts": [],
            "hcaptcha_auto_solve": True,
            "hcaptcha_auto_open": False,
            "recaptcha_auto_solve": False,
            "recaptcha_auto_open": False,
            "awscaptcha_auto_solve": False,
            "awscaptcha_auto_open": False,
            "funcaptcha_auto_solve": False,
            "funcaptcha_auto_open": False,
            "geetest_auto_solve": False,
            "geetest_auto_open": False,
            "lemincaptcha_auto_solve": False,
            "lemincaptcha_auto_open": False,
            "perimeterx_auto_solve": False,
            "textcaptcha_auto_solve": False,
            "turnstile_auto_solve": False,
            "hcaptcha_solve_delay_time": 3000,
        }
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = self._make_extension(extension_dir, manifest)
            report = Nopecha(api_key=api_key, extension_path=extension_dir).update_files()
            written = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._assert_scripts_untouched(extension_dir)

        self.assertEqual(report["modified"], ["manifest.json"])
        self.assertEqual(written["nopecha"]["key"], api_key)
        self.assertEqual(written["nopecha"]["keys"], [])
        self.assertEqual(written["nopecha"]["disabled_hosts"], [])
        self.assertEqual(written["nopecha"]["hcaptcha_solve_delay_time"], 3000)
        self.assertIs(written["nopecha"]["enabled"], True)
        self.assertEqual(written["key"], AUTOMATION_MANIFEST["key"])
        for name, value in written["nopecha"].items():
            if name.endswith("_auto_solve") or name.endswith("_auto_open"):
                self.assertIs(value, True, name)

    def test_missing_or_non_dict_nopecha_settings_become_a_dict(self):
        cases = (
            {k: v for k, v in AUTOMATION_MANIFEST.items() if k != "nopecha"},
            {**AUTOMATION_MANIFEST, "nopecha": "not-a-dict"},
        )
        for manifest in cases:
            with self.subTest(nopecha=manifest.get("nopecha", "<missing>")):
                with tempfile.TemporaryDirectory() as tmp:
                    extension_dir = Path(tmp)
                    manifest_path = self._make_extension(extension_dir, manifest)
                    Nopecha(api_key="sub_test_key", extension_path=extension_dir).update_files()
                    written = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(written["nopecha"]["key"], "sub_test_key")
                self.assertEqual(written["key"], AUTOMATION_MANIFEST["key"])
                if manifest.get("nopecha") == "not-a-dict":
                    self.assertEqual(
                        written["nopecha"],
                        {"enabled": True, "key": "sub_test_key"},
                    )

    def test_extension_path_resolves_absolute_and_relative_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp) / "unpacked"
            extension_dir.mkdir()
            self._make_extension(extension_dir)
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                relative = Nopecha(api_key="sub_test_key", extension_path="unpacked")
                self.assertEqual(relative.extension_path, "unpacked")
                self.assertEqual(relative.extension_absolute_path, os.path.abspath("unpacked"))
                manifest_file = relative.get_file("/manifest.json")
                popup_file = relative.get_file("\\popup.js")
                self.assertEqual(
                    manifest_file.path,
                    os.path.join(relative.extension_absolute_path, "manifest.json"),
                )
                self.assertEqual(
                    popup_file.path,
                    os.path.join(relative.extension_absolute_path, "popup.js"),
                )

                absolute = Nopecha(api_key="sub_test_key")
                absolute.extension_path = extension_dir
                self.assertEqual(absolute.extension_absolute_path, os.path.abspath(extension_dir))
            finally:
                os.chdir(previous)

    def test_load_patches_extension_directory_without_downloading_or_storing_key(self):
        api_key = "sub_test_key_load"
        storage_path = Path(get_cache_file_path())
        existed = storage_path.exists()
        before = storage_path.read_text(encoding="utf-8") if existed else None
        PackageStorage.refresh()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                extension_dir = Path(tmp)
                manifest_path = self._make_extension(extension_dir)
                ext = Nopecha(api_key=api_key, extension_path=extension_dir)

                def fail_download() -> None:
                    raise AssertionError("download() must not be called")

                ext.download = fail_download
                plain = ext.load(with_command_line_option=False)
                flagged = ext.load()
                written = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._assert_scripts_untouched(extension_dir)

            self.assertEqual(plain, ext.extension_absolute_path)
            self.assertEqual(flagged, f"--load-extension={ext.extension_absolute_path}")
            self.assertNotIn("api_key", ext.kwargs)
            self._assert_other_settings_preserved(written, api_key)
            PackageStorage.refresh()
            after = storage_path.read_text(encoding="utf-8") if storage_path.exists() else None
            self.assertEqual(after, before)
            self.assertNotIn(api_key, after or "")
        finally:
            if before is None:
                if storage_path.exists():
                    storage_path.unlink()
            else:
                storage_path.write_text(before, encoding="utf-8")
            PackageStorage.refresh()

    def test_load_missing_manifest_raises_without_downloading(self):
        with tempfile.TemporaryDirectory() as tmp:
            ext = Nopecha(api_key="sub_test_key", extension_path=tmp)

            def fail_download() -> None:
                raise AssertionError("download() must not be called")

            ext.download = fail_download
            with self.assertRaises(FileNotFoundError):
                ext.load()

    def test_load_raises_when_manifest_json_cannot_be_patched(self):
        for payload in ("{not json", "[]"):
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as tmp:
                    extension_dir = Path(tmp)
                    (extension_dir / "manifest.json").write_text(payload, encoding="utf-8")
                    ext = Nopecha(api_key="sub_test_key", extension_path=extension_dir)

                    def fail_download() -> None:
                        raise AssertionError("download() must not be called")

                    ext.download = fail_download
                    with self.assertRaises((ValueError, TypeError, OSError)):
                        ext.load()

    def test_quick_patch_file_only_updates_manifest_json(self):
        api_key = "quick-patch-key"
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = self._make_extension(extension_dir)
            ext = Nopecha(api_key=api_key, extension_path=extension_dir)

            self.assertFalse(ext.quick_patch_file("popup.js"))
            self.assertFalse(ext.quick_patch_file("/popup.html"))
            self.assertEqual((extension_dir / "popup.js").read_text(encoding="utf-8"), JS_SOURCE)

            self.assertTrue(ext.quick_patch_file("/manifest.json"))
            written = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._assert_other_settings_preserved(written, api_key)

            compact = manifest_path.read_bytes()
            self.assertTrue(ext.quick_patch_file("\\manifest.json"))
            self.assertEqual(manifest_path.read_bytes(), compact)

            manifest_path.write_text("{not json", encoding="utf-8")
            self.assertFalse(ext.quick_patch_file("manifest.json"))
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), "{not json")


class PatcherCliTest(unittest.TestCase):
    def _cli_env(self, **updates: str) -> dict[str, str]:
        env = os.environ.copy()
        env.pop("NOPECHA_API_KEY", None)
        env.pop("CUSTOM_NOPECHA_KEY", None)
        env.update(updates)
        return env

    def _run_cli(self, args: list[str], env: dict[str, str], stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "nopecha_extension.patcher", *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_dry_run_is_the_default_and_write_flag_persists_the_key(self):
        api_key = "cli-write-key"
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = extension_dir / "manifest.json"
            manifest_path.write_text(json.dumps(AUTOMATION_MANIFEST), encoding="utf-8")
            (extension_dir / "popup.js").write_text(JS_SOURCE, encoding="utf-8")
            original = manifest_path.read_bytes()
            env = self._cli_env(NOPECHA_API_KEY=api_key)

            preview = self._run_cli([str(extension_dir)], env)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            preview_report = json.loads(preview.stdout)
            self.assertEqual(preview_report["modified"], ["manifest.json"])
            self.assertEqual(preview_report["skipped"], [])
            self.assertNotIn(api_key, preview.stdout)
            self.assertEqual(manifest_path.read_bytes(), original)

            written = self._run_cli([str(extension_dir), "--write"], env)
            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertEqual(json.loads(written.stdout)["modified"], ["manifest.json"])
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["nopecha"]["key"], api_key)
            self.assertEqual(saved["key"], AUTOMATION_MANIFEST["key"])
            self.assertEqual((extension_dir / "popup.js").read_text(encoding="utf-8"), JS_SOURCE)

            again = self._run_cli([str(extension_dir), "--write"], env)
            self.assertEqual(json.loads(again.stdout)["skipped"], ["manifest.json"])

    def test_key_env_and_key_stdin_supply_the_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = extension_dir / "manifest.json"
            manifest_path.write_text(json.dumps(AUTOMATION_MANIFEST), encoding="utf-8")

            from_env = self._run_cli(
                [str(extension_dir), "--key-env", "CUSTOM_NOPECHA_KEY", "--write"],
                self._cli_env(CUSTOM_NOPECHA_KEY="from-env"),
            )
            self.assertEqual(from_env.returncode, 0, from_env.stderr)
            self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8"))["nopecha"]["key"], "from-env")

            from_stdin = self._run_cli(
                [str(extension_dir), "--key-stdin", "--write"],
                self._cli_env(),
                stdin=SPECIAL_KEY + "\n",
            )
            self.assertEqual(from_stdin.returncode, 0, from_stdin.stderr)
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["nopecha"]["key"], SPECIAL_KEY)
            self.assertNotIn(SPECIAL_KEY, from_stdin.stdout)

    def test_read_only_manifest_write_is_reported(self):
        if os.geteuid() == 0:
            self.skipTest("mode 0o444 does not block writes when running as root")

        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = extension_dir / "manifest.json"
            manifest_path.write_text(json.dumps(AUTOMATION_MANIFEST), encoding="utf-8")
            original_mode = manifest_path.stat().st_mode
            original = manifest_path.read_bytes()
            manifest_path.chmod(0o444)
            try:
                report = Nopecha(api_key="sub_test_key", extension_path=extension_dir).update_files()
                self.assertEqual(report["modified"], [])
                self.assertTrue(report["errors"])
                self.assertEqual(manifest_path.read_bytes(), original)

                completed = self._run_cli(
                    [str(extension_dir), "--write"],
                    self._cli_env(NOPECHA_API_KEY="sub_test_key"),
                )
                self.assertEqual(completed.returncode, 1, completed.stderr)
                cli_report = json.loads(completed.stdout)
                self.assertEqual(cli_report["modified"], [])
                self.assertTrue(cli_report["errors"])
                self.assertEqual(manifest_path.read_bytes(), original)
            finally:
                manifest_path.chmod(original_mode)

    def test_missing_key_or_extra_positional_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = extension_dir / "manifest.json"
            manifest_path.write_text(json.dumps(AUTOMATION_MANIFEST), encoding="utf-8")
            original = manifest_path.read_bytes()

            missing = self._run_cli([str(extension_dir), "--write"], self._cli_env())
            self.assertEqual(missing.returncode, 2)
            self.assertIn("NOPECHA_API_KEY", missing.stderr)
            self.assertEqual(manifest_path.read_bytes(), original)

            extra = self._run_cli(
                [str(extension_dir), "positional-secret", "--write"],
                self._cli_env(NOPECHA_API_KEY="from-env"),
            )
            self.assertNotEqual(extra.returncode, 0)
            self.assertEqual(manifest_path.read_bytes(), original)
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertNotEqual(saved["nopecha"]["key"], "positional-secret")


if __name__ == "__main__":
    unittest.main()
