import json
import tempfile
import unittest
from pathlib import Path

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


class AutomationManifestKeyTest(unittest.TestCase):
    def test_automation_build_writes_api_key_into_nopecha_settings(self):
        api_key = "sub_test_key_9f3a"
        with tempfile.TemporaryDirectory() as tmp:
            extension_dir = Path(tmp)
            manifest_path = extension_dir / "manifest.json"
            manifest_path.write_text(json.dumps(AUTOMATION_MANIFEST), encoding="utf-8")

            ext = Nopecha(api_key=api_key)
            ext.extension_path = str(extension_dir)
            ext.update_files()

            written = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(written["nopecha"]["key"], api_key)
        self.assertEqual(written["nopecha"]["hcaptcha_auto_solve"], True)
        self.assertEqual(written["nopecha"]["keys"], [])
        self.assertEqual(written["key"], AUTOMATION_MANIFEST["key"])


if __name__ == "__main__":
    unittest.main()
