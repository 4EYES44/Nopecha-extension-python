# Nopecha Extension Python

Write a NopeCHA API key into an unpacked [Automation Build](https://developers.nopecha.com/guides/extension_advanced/#automation-build) (`chromium_automation.zip`).

The Automation Build reads its key from the Nopecha Manifest Config, `manifest["nopecha"]["key"]` in `manifest.json`. This package sets that field, turns on every captcha `*_auto_solve` and `*_auto_open` flag, and sets `enabled` to `true`. It leaves the rest of the Nopecha Manifest Config alone, including delay times and selectors, and it never rewrites the top-level `"key"` (the Chrome extension public key). It does not modify JavaScript or HTML, and it does not download the Web Store CRX.

If you omit `extension_path`, `load()` downloads `chromium_automation.zip` from NopeCHA GitHub releases into `extensions/NopeCHA` and re-downloads when `manifest["version_name"]` differs from the latest release tag. Pass `version="0.6.1"` to pin a tag. A user-supplied Extension Directory is never overwritten by a download.

The API key stays in the process. `load()` does not call `chrome_extension_python`'s storage writer, so the key is not saved in `site-packages/chrome_extension_python/package_storage.json`.

Requires Python 3.8 or newer. The package is published on [PyPI](https://pypi.org/project/nopecha-extension/).

```bash
pip install nopecha-extension
```

## Patch the Extension Directory

`extension_path` is the unpacked Automation Build directory. `update_files()` rewrites `manifest.json` when the API key differs or any captcha type is still disabled. A second call with the same key and all captcha types already enabled leaves the file unchanged and reports it under `skipped`.

```python
import os

from nopecha_extension import Nopecha

ext = Nopecha(
    api_key=os.environ["NOPECHA_API_KEY"],
    extension_path="path/to/chromium_automation",
)
report = ext.update_files()
print(report)
```

A changed key produces:

```json
{
  "modified": [
    "manifest.json"
  ],
  "skipped": [],
  "errors": []
}
```

An empty string, a whitespace-only string, `None`, or any non-string raises `ValueError` (`api_key must be a non-empty string`) before the file is opened for writing.

## Load it in Botasaurus

Install Botasaurus separately (`pip install botasaurus`). Passing the `Nopecha` instance in `extensions` makes Botasaurus call `load()`, which downloads the Automation Build if needed, patches `manifest.json`, and returns Chrome's `--load-extension` flag. `load()` raises `FileNotFoundError` when a user-supplied Extension Directory has no `manifest.json`.

```python
import os

from botasaurus.browser import Driver, browser

from nopecha_extension import Nopecha

ext = Nopecha(api_key=os.environ["NOPECHA_API_KEY"])

@browser(extensions=[ext])
def open_example(driver: Driver, data):
    driver.get("https://example.com/")
    driver.prompt()

if __name__ == "__main__":
    open_example()
```

Point `extension_path` at an unpacked Automation Build to skip the download. `load(with_command_line_option=False)` returns the Extension Directory path instead of the flag.

## Command line

The key is read from the environment or stdin, never from a positional argument. The default is a dry run: nothing is written unless `--write` is passed. `--key-env` defaults to `NOPECHA_API_KEY`.

```bash
export NOPECHA_API_KEY="YOUR_NOPECHA_KEY"

python -m nopecha_extension.patcher path/to/chromium_automation

python -m nopecha_extension.patcher path/to/chromium_automation --write

python -m nopecha_extension.patcher path/to/chromium_automation --key-env NOPECHA_API_KEY --write

printf '%s\n' "$NOPECHA_API_KEY" | python -m nopecha_extension.patcher path/to/chromium_automation --key-stdin --write
```

A missing environment variable prints `Environment variable NOPECHA_API_KEY is not set` to stderr and exits with status 2. The manifest is not changed.
