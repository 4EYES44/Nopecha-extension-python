from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from nopecha_extension.patcher import Nopecha


MARKER = "automation-build-marker.txt"

AUTOMATION_MANIFEST = {
    "nopecha": {
        "key": "",
        "keys": [],
        "enabled": True,
        "hcaptcha_auto_solve": True,
        "hcaptcha_auto_open": True,
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
        "turnstile_auto_solve": True,
    },
    "name": "NopeCHA: CAPTCHA Solver",
    "version": "0.6.1",
    "version_name": "v0.6.1",
    "manifest_version": 3,
    "key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKC-extension-public-key",
}


@contextmanager
def _in_temp_cwd():
    with tempfile.TemporaryDirectory() as tmp:
        previous = os.getcwd()
        os.chdir(tmp)
        try:
            yield tmp
        finally:
            os.chdir(previous)


def _automation_zip(manifest: dict | None = None) -> bytes:
    payload = AUTOMATION_MANIFEST if manifest is None else manifest
    buf = BytesIO()
    with ZipFile(buf, "w") as archive:
        archive.writestr("manifest.json", json.dumps(payload))
        archive.writestr(MARKER, "from-github-automation-zip")
        archive.writestr("popup.js", "apiKey: ''\n")
    return buf.getvalue()


class AutomationBuildDownloadTest(unittest.TestCase):
    def test_load_without_extension_directory_fetches_automation_build(self):
        zip_bytes = _automation_zip()
        fetched: list[str] = []

        def fake_fetch_bytes(url: str) -> bytes:
            fetched.append(url)
            if "clients2.google.com" in url:
                raise AssertionError("must not download the Web Store CRX")
            return zip_bytes

        with _in_temp_cwd():
            with patch("nopecha_extension.patcher._fetch_bytes", fake_fetch_bytes), patch(
                "nopecha_extension.patcher._fetch_json",
                return_value={"tag_name": "0.6.1"},
            ):
                ext = Nopecha(api_key="sub_test_key")
                path = ext.load(with_command_line_option=False)
                flagged = ext.load()
                written = json.loads(
                    (Path(path) / "manifest.json").read_text(encoding="utf-8")
                )
                marker_exists = (Path(path) / MARKER).is_file()
                absolute_path = ext.extension_absolute_path

        self.assertEqual(len(fetched), 1)
        self.assertTrue(all("chromium_automation.zip" in url for url in fetched))
        self.assertTrue(marker_exists)
        self.assertEqual(path, absolute_path)
        self.assertEqual(flagged, f"--load-extension={absolute_path}")
        self.assertEqual(written["nopecha"]["key"], "sub_test_key")
        self.assertEqual(written["key"], AUTOMATION_MANIFEST["key"])
        self.assertIs(written["nopecha"]["enabled"], True)
        for name, value in written["nopecha"].items():
            if name.endswith("_auto_solve") or name.endswith("_auto_open"):
                self.assertIs(value, True, name)

    def test_load_redownloads_when_cached_version_differs_from_latest_release(self):
        old_manifest = json.loads(json.dumps(AUTOMATION_MANIFEST))
        old_manifest["version"] = "0.6.0"
        old_manifest["version_name"] = "v0.6.0"
        new_manifest = json.loads(json.dumps(AUTOMATION_MANIFEST))
        new_manifest["version"] = "0.6.1"
        new_manifest["version_name"] = "v0.6.1"
        zips = {
            "0.6.0": _automation_zip(old_manifest),
            "0.6.1": _automation_zip(new_manifest),
        }
        latest = {"tag": "0.6.0"}
        fetched: list[str] = []

        def fake_fetch_bytes(url: str) -> bytes:
            fetched.append(url)
            return zips[latest["tag"]]

        def fake_fetch_json(url: str) -> dict:
            return {"tag_name": latest["tag"]}

        with _in_temp_cwd():
            with patch("nopecha_extension.patcher._fetch_bytes", fake_fetch_bytes), patch(
                "nopecha_extension.patcher._fetch_json", fake_fetch_json
            ):
                ext = Nopecha(api_key="sub_test_key")
                path = Path(ext.load(with_command_line_option=False))
                (path / MARKER).write_text("old-cache", encoding="utf-8")
                latest["tag"] = "0.6.1"
                ext.load(with_command_line_option=False)
                marker = (path / MARKER).read_text(encoding="utf-8")
                written = json.loads((path / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(marker, "from-github-automation-zip")
        self.assertEqual(written["version_name"], "v0.6.1")
        self.assertEqual(written["nopecha"]["key"], "sub_test_key")
        self.assertGreaterEqual(len(fetched), 2)

    def test_load_redownloads_when_cached_manifest_has_no_version_name(self):
        stale_manifest = json.loads(json.dumps(AUTOMATION_MANIFEST))
        stale_manifest["version"] = "0.6.1"
        stale_manifest.pop("version_name", None)
        zips = [_automation_zip(stale_manifest), _automation_zip()]
        fetched: list[str] = []

        def fake_fetch_bytes(url: str) -> bytes:
            fetched.append(url)
            return zips[min(len(fetched) - 1, 1)]

        with _in_temp_cwd():
            with patch("nopecha_extension.patcher._fetch_bytes", fake_fetch_bytes), patch(
                "nopecha_extension.patcher._fetch_json",
                return_value={"tag_name": "0.6.1"},
            ):
                ext = Nopecha(api_key="sub_test_key")
                path = Path(ext.load(with_command_line_option=False))
                (path / MARKER).write_text("old-cache", encoding="utf-8")
                ext.load(with_command_line_option=False)
                marker = (path / MARKER).read_text(encoding="utf-8")

        self.assertEqual(len(fetched), 2)
        self.assertEqual(marker, "from-github-automation-zip")

    def test_load_pinned_version_fetches_that_release(self):
        zip_bytes = _automation_zip()
        fetched: list[str] = []

        def fake_fetch_bytes(url: str) -> bytes:
            fetched.append(url)
            return zip_bytes

        with _in_temp_cwd():
            with patch("nopecha_extension.patcher._fetch_bytes", fake_fetch_bytes):
                ext = Nopecha(api_key="sub_test_key", version="0.6.1")
                path = ext.load(with_command_line_option=False)
                written = json.loads(
                    (Path(path) / "manifest.json").read_text(encoding="utf-8")
                )

        self.assertEqual(fetched, [
            "https://github.com/NopeCHALLC/nopecha-extension/releases/download/"
            "0.6.1/chromium_automation.zip"
        ])
        self.assertEqual(written["nopecha"]["key"], "sub_test_key")


if __name__ == "__main__":
    unittest.main()
