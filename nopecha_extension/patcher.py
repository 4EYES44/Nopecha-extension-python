from chrome_extension_python import Extension
import re
import json

class Nopecha(Extension):
    """
    Helper class to inject an API key into a downloaded "Nopecha" Chrome extension folder.

    Usage:
        from nopecha_extension import Nopecha
        ext = Nopecha(api_key="YOUR_KEY_HERE")
        ext.update_files()  # will try to patch JS files and manifest/popup files

    Notes:
    - This class makes a best-effort set of safe textual replacements. Always review and test the output.
    - It does not change binary files or images.
    - It attempts several common patterns where an API key might be stored in JS/HTML.
    """

    def __init__(self, api_key: str, extension_id: str = "dknlfmjaanfblgfdfebhijalfmhmjjjo", extension_name: str = "NopeCHA"):
        # fallback extension_id is provided so the base class can be initialized even if you don't know the store id
        super().__init__(
            extension_id=extension_id,
            extension_name=extension_name,
            api_key=api_key,
        )
        self.api_key = api_key

    def _pattern_replacements(self, content: str, api_key: str) -> str:
        """Run a set of safe regex replacements to embed the API key into JS/HTML content.

        The order matters: try to match explicit key holders first, then more general patterns.
        """
        original = content

        # common JS/HTML patterns that might contain an empty API key placeholder
        replacements = [
            # JS object style: apiKey: ''  OR apiKey: ""
            (r"apiKey\s*:\s*['\"]{0,1}['\"]", f"apiKey: '{api_key}'"),
            (r"apiKey\s*:\s*['\"]{0,1}\s*['\"]", f"apiKey: '{api_key}'"),

            # explicit placeholder tokens
            (r"NOPECHA[_-]?API[_-]?KEY", api_key),
            (r"NOPECHA_APIKEY", api_key),
            (r"NOPECHA_KEY", api_key),

            # window globals: window.NOPECHA_API_KEY = ''
            (r"window\.(NOPECHA[_A-Z0-9]*)\s*=\s*['\"].*?['\"]", f"window.\\1 = '{api_key}'"),

            # generic patterns: api_key: '', "api_key":""
            (r"api_key\s*[:=]\s*['\"].*?['\"]", f"api_key: '{api_key}'"),

            # some scripts use a defaultConfig return style (like the Capsolver example)
            (r"return\s+e\.defaultConfig", f"return {{ ...e.defaultConfig, apiKey: '{api_key}' }}"),

            # HTML inputs default value: <input ... value="" data-key-placeholder>
            (r"(value=)['\"]{0,1}['\"]", f"\1'{api_key}'"),
        ]

        # apply replacements sequentially; use re.sub with flags to handle multiline
        updated = content
        for pat, repl in replacements:
            try:
                updated = re.sub(pat, repl, updated, flags=re.IGNORECASE | re.DOTALL)
            except re.error:
                # if a pattern is malformed, skip it (shouldn't happen)
                continue

        # If nothing changed, return original to avoid masking (caller can detect no-change)
        return updated if updated != original else content

    def update_files(self, api_key: str | None = None) -> dict:
        """Main entrypoint: update multiple files in the extension.

        Returns a small report dict with which files were touched (best-effort).
        """
        api_key = api_key or self.api_key
        report = {"modified": [], "skipped": [], "errors": []}

        # 1) Update all JS files discovered by the provided helper
        try:
            js_files = self.get_js_files()  # expected helper from the Extension base
        except Exception as e:
            js_files = []
            report['errors'].append(f"get_js_files() failed: {e}")

        for js in js_files:
            try:
                def make_updater(content):
                    new = self._pattern_replacements(content, api_key)
                    return new

                js.update_contents(make_updater)
                report['modified'].append(js.path if hasattr(js, 'path') else getattr(js, 'name', str(js)))
            except Exception as e:
                report['errors'].append(f"Failed to update JS file {getattr(js,'path',str(js))}: {e}")

        # 2) Update a set of typical files present in a Nopecha download
        likely_files = [
            '/popup.js',
            '/popup.html',
            '/setup.html',
            '/background.js',
            '/eventhook.js',
            '/locate.js',
            '/manifest.json',
        ]

        for path in likely_files:
            try:
                file = self.get_file(path)
            except Exception:
                report['skipped'].append(path)
                continue

            try:
                if path.endswith('.json'):
                    # manifest.json special handling: attempt to parse and inject "storage" permission
                    try:
                        raw = file.get_contents() if hasattr(file, "get_contents") else file.read()
                        manifest = json.loads(raw)
                        changed = False
                        perms = manifest.get('permissions', [])
                        if 'storage' not in perms:
                            perms.append('storage')
                            manifest['permissions'] = perms
                            changed = True

                        # also ensure host permissions accomodate external API calls if missing
                        host_perms = manifest.get('host_permissions', [])
                        if host_perms and 'https://*/*' not in host_perms:
                            host_perms.append('https://*/*')
                            manifest['host_permissions'] = host_perms
                            changed = True

                        # Automation builds load the API key from manifest["nopecha"]["key"].
                        nopecha_settings = manifest.get("nopecha")
                        if isinstance(nopecha_settings, dict):
                            nopecha_settings["key"] = api_key
                            changed = True

                        if changed:
                            # write back prettified JSON
                            new_content = json.dumps(manifest, indent=2)
                            file.update_contents(lambda _c, nc=new_content: nc)
                            report['modified'].append(path)
                        else:
                            report['skipped'].append(path)
                    except Exception:
                        # fallback to regex replacement if JSON parse fails
                        file.update_contents(lambda c: self._pattern_replacements(c, api_key))
                        report['modified'].append(path)
                else:
                    file.update_contents(lambda c: self._pattern_replacements(c, api_key))
                    report['modified'].append(path)
            except Exception as e:
                report['errors'].append(f"Failed to patch {path}: {e}")

        # 3) Final helpful tweak: if popup.html contains an input for the API key, set its value
        try:
            popup = self.get_file('/popup.html')
            def popup_updater(content):
                # try to set a known input id or name
                content2 = re.sub(r"(<input[^>]+id=['\"]?(apiKey|nopecha-key|apikey)['\"]?[^>]*value=['\"]).*?(['\"])",
                                  rf"\1{api_key}\3",
                                  content,
                                  flags=re.IGNORECASE|re.DOTALL)
                # fallback: replace placeholder text
                content2 = content2.replace('NOPECHA_API_KEY', api_key)
                return content2

            popup.update_contents(popup_updater)
            report['modified'].append('/popup.html')
        except Exception:
            pass

        return report

    def quick_patch_file(self, path: str, api_key: str | None = None) -> bool:
        """Convenience: patch a single file path. Returns True if patched without exception.
        """
        api_key = api_key or self.api_key
        try:
            file = self.get_file(path)
        except Exception:
            return False

        try:
            file.update_contents(lambda c: self._pattern_replacements(c, api_key))
            return True
        except Exception:
            return False


# If the user executes this file directly as a small test harness, do a dry-run style report.
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Nopecha extension patcher (dry-run).')
    parser.add_argument('api_key', help='Nopecha API key to inject')
    args = parser.parse_args()

    ext = Nopecha(args.api_key)
    report = ext.update_files()
    print('Patch report:')
    print(json.dumps(report, indent=2))
