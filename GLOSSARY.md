# Nopecha Extension Python

A Python configuration and loading wrapper for the NopeCHA browser extension, built on `chrome_extension_python`.

## Language

**Automation Build**:
The official `chromium_automation.zip` distribution published on `NopeCHALLC/nopecha-extension` GitHub releases, configured via `manifest.json` rather than runtime UI popups.
_Avoid_: Web Store build, CRX build

**Nopecha Manifest Config**:
The `"nopecha"` dictionary inside `manifest.json` (`manifest["nopecha"]`) where the Automation Build reads its API key and solver settings at startup.
_Avoid_: Top-level manifest `"key"` (which is the Chrome extension's RSA public key), JS/HTML placeholders

**Extension Directory**:
The local filesystem directory containing the unpacked Automation Build (and its `manifest.json`).
_Avoid_: Extension path, CRX cache
