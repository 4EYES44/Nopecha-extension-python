from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from io import BytesIO
from typing import Any
from zipfile import BadZipFile, ZipFile

from requests import get as http_get

from chrome_extension_python import Extension, File, relative_path

_MANIFEST_NAME = "manifest.json"
_MANIFEST_READ_ERRORS = (OSError, UnicodeError, json.JSONDecodeError, TypeError)
_AUTOMATION_ZIP_LATEST = (
    "https://github.com/NopeCHALLC/nopecha-extension/releases/latest/download/"
    "chromium_automation.zip"
)
_AUTOMATION_ZIP_TAG = (
    "https://github.com/NopeCHALLC/nopecha-extension/releases/download/"
    "{tag}/chromium_automation.zip"
)
_LATEST_RELEASE_API = (
    "https://api.github.com/repos/NopeCHALLC/nopecha-extension/releases/latest"
)


def _fetch_bytes(url: str) -> bytes:
    response = http_get(url, timeout=60)
    response.raise_for_status()
    return response.content


def _fetch_json(url: str) -> dict[str, Any]:
    response = http_get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("GitHub release response must be a JSON object")
    return payload


def _normalized_version(value: str) -> str:
    return value.strip().lstrip("vV")


def _latest_release_tag() -> str:
    tag = _fetch_json(_LATEST_RELEASE_API).get("tag_name")
    if not isinstance(tag, str) or tag.strip() == "":
        raise ValueError("GitHub latest release is missing tag_name")
    return tag.strip()


def _extract_zip(payload: bytes, dest: str) -> None:
    dest = os.path.abspath(dest)
    try:
        archive = ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise ValueError("Automation Build download is not a valid zip") from exc
    with archive:
        for info in archive.infolist():
            target = os.path.abspath(os.path.join(dest, info.filename))
            if target != dest and not target.startswith(dest + os.sep):
                raise ValueError(f"unsafe path in Automation Build zip: {info.filename}")
        archive.extractall(dest)


def _validated_api_key(api_key: str) -> str:
    if isinstance(api_key, str) and api_key.strip() != "":
        return api_key
    raise ValueError("api_key must be a non-empty string")


def _is_captcha_toggle(name: str) -> bool:
    return name.endswith("_auto_solve") or name.endswith("_auto_open")


def _with_captcha_types_enabled(settings: dict[str, Any]) -> dict[str, Any]:
    updated = dict(settings)
    updated["enabled"] = True
    for name in list(updated):
        if _is_captcha_toggle(name):
            updated[name] = True
    return updated


def _nopecha_config_matches(settings: dict[str, Any], api_key: str) -> bool:
    if settings.get("key") != api_key or settings.get("enabled") is not True:
        return False
    return all(
        value is True
        for name, value in settings.items()
        if _is_captcha_toggle(name)
    )


def _with_nopecha_config(manifest: dict[str, Any], api_key: str) -> dict[str, Any] | None:
    nopecha_settings = manifest.get("nopecha")
    if isinstance(nopecha_settings, dict) and _nopecha_config_matches(nopecha_settings, api_key):
        return None

    if not isinstance(nopecha_settings, dict):
        nopecha_settings = {}
    else:
        nopecha_settings = dict(nopecha_settings)
    nopecha_settings = _with_captcha_types_enabled(nopecha_settings)
    nopecha_settings["key"] = api_key

    updated = dict(manifest)
    updated["nopecha"] = nopecha_settings
    return updated


def _manifest_read_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "manifest.json not found"
    if isinstance(exc, json.JSONDecodeError):
        return f"manifest.json is not valid JSON: {exc}"
    if isinstance(exc, TypeError):
        return str(exc)
    return f"Failed to read manifest.json: {exc}"


class Nopecha(Extension):
    """Point an unpacked Automation Build at a NopeCHA API key.

    The key is written to the Nopecha Manifest Config, ``manifest["nopecha"]["key"]``,
    and every captcha ``*_auto_solve`` / ``*_auto_open`` flag is turned on.
    It is not passed into ``chrome_extension_python``, so ``load()`` does not
    persist it in ``package_storage.json``.

    When no Extension Directory is supplied, ``load()`` downloads
    ``chromium_automation.zip`` into ``extensions/NopeCHA``.
    """

    def __init__(
        self,
        api_key: str,
        extension_path: str | os.PathLike[str] | None = None,
        version: str | None = None,
        extension_id: str = "dknlfmjaanfblgfdfebhijalfmhmjjjo",
        extension_name: str = "NopeCHA",
    ) -> None:
        key = _validated_api_key(api_key)
        self._user_supplied_path = False
        self._count_path_as_user_supplied = False
        super().__init__(
            extension_id=extension_id,
            extension_name=extension_name,
        )
        self._count_path_as_user_supplied = True
        self.api_key = key
        self.version = version
        if extension_path is not None:
            self.extension_path = extension_path

    @property
    def extension_path(self) -> str:
        return self._extension_path

    @extension_path.setter
    def extension_path(self, extension_path: str | os.PathLike[str]) -> None:
        path = os.fspath(extension_path)
        self._extension_path = path
        if os.path.isabs(path):
            self.extension_absolute_path = os.path.abspath(path)
        else:
            self.extension_absolute_path = relative_path(path)
        if self._count_path_as_user_supplied:
            self._user_supplied_path = True

    def get_file(self, path: str) -> File:
        relative = path.lstrip("/\\")
        return File(os.path.join(self.extension_absolute_path, relative))

    def _api_key_for_patch(self, api_key: str | None) -> str:
        if api_key is None:
            return _validated_api_key(self.api_key)
        return _validated_api_key(api_key)

    def _read_manifest(self, relative_manifest_path: str) -> dict[str, Any]:
        parsed = json.loads(self.get_file(relative_manifest_path).get_contents())
        if isinstance(parsed, dict):
            return parsed
        raise TypeError("manifest.json must contain a JSON object")

    def _write_manifest(self, manifest: dict[str, Any], relative_manifest_path: str = _MANIFEST_NAME) -> None:
        rendered = json.dumps(manifest, indent=2) + "\n"
        self.get_file(relative_manifest_path).write_contents(rendered)

    def _manifest_for_write(self, api_key: str | None) -> dict[str, Any] | None:
        key = self._api_key_for_patch(api_key)
        return _with_nopecha_config(self._read_manifest(_MANIFEST_NAME), key)

    def _plan_update(self, api_key: str | None) -> tuple[dict[str, list[str]], dict[str, Any] | None]:
        report: dict[str, list[str]] = {"modified": [], "skipped": [], "errors": []}
        try:
            updated = self._manifest_for_write(api_key)
        except _MANIFEST_READ_ERRORS as exc:
            report["errors"].append(_manifest_read_error(exc))
            return report, None

        if updated is None:
            report["skipped"].append(_MANIFEST_NAME)
            return report, None
        return report, updated

    def update_files(self, api_key: str | None = None) -> dict[str, list[str]]:
        """Write the API key and enable captcha types in ``manifest.json``.

        A matching key with every captcha type already enabled leaves the file
        untouched. ``manifest.json`` is listed in ``modified`` only after a
        successful write.
        """
        report, updated = self._plan_update(api_key)
        if updated is None:
            return report
        try:
            self._write_manifest(updated)
        except OSError as exc:
            report["errors"].append(f"Failed to write manifest.json: {exc}")
            return report
        report["modified"].append(_MANIFEST_NAME)
        return report

    def quick_patch_file(self, path: str = _MANIFEST_NAME, api_key: str | None = None) -> bool:
        """Patch one ``manifest.json``. Return False when the path or file cannot be patched."""
        relative_manifest_path = path.lstrip("/\\")
        if os.path.basename(relative_manifest_path) != _MANIFEST_NAME:
            return False
        key = self._api_key_for_patch(api_key)
        try:
            updated = _with_nopecha_config(self._read_manifest(relative_manifest_path), key)
            if updated is not None:
                self._write_manifest(updated, relative_manifest_path)
        except _MANIFEST_READ_ERRORS:
            return False
        return True

    def _cached_version_name(self) -> str | None:
        try:
            manifest = self._read_manifest(_MANIFEST_NAME)
        except _MANIFEST_READ_ERRORS:
            return None
        name = manifest.get("version_name")
        if isinstance(name, str) and name.strip() != "":
            return name.strip()
        return None

    def _desired_tag(self) -> str:
        if self.version:
            return self.version
        return _latest_release_tag()

    def _cache_is_stale(self) -> bool:
        cached = self._cached_version_name()
        if cached is None:
            return True
        return _normalized_version(cached) != _normalized_version(self._desired_tag())

    def _automation_zip_url(self) -> str:
        if self.version:
            return _AUTOMATION_ZIP_TAG.format(tag=self.version)
        return _AUTOMATION_ZIP_LATEST

    def download(self) -> None:
        """Fetch the Automation Build zip into the Extension Directory cache."""
        if self._user_supplied_path:
            return
        payload = _fetch_bytes(self._automation_zip_url())
        dest = self.extension_absolute_path
        if os.path.exists(dest):
            shutil.rmtree(dest)
        os.makedirs(dest, exist_ok=True)
        _extract_zip(payload, dest)

    def load(self, with_command_line_option: bool = True) -> str:
        """Patch ``manifest.json`` and return the Chrome load flag.

        When no Extension Directory was supplied, fetches the Automation Build
        first. Raises ``FileNotFoundError`` when the manifest is missing. Read
        and write failures propagate (``ValueError``, ``TypeError``, or
        ``OSError``) instead of returning a path for an unpatched manifest.
        """
        manifest_path = os.path.join(self.extension_absolute_path, _MANIFEST_NAME)
        if not self._user_supplied_path and (
            not os.path.isfile(manifest_path)
            or self.force_update
            or self._cache_is_stale()
        ):
            self.download()
            manifest_path = os.path.join(self.extension_absolute_path, _MANIFEST_NAME)
        if not os.path.isfile(manifest_path):
            raise FileNotFoundError(manifest_path)
        updated = self._manifest_for_write(self.api_key)
        if updated is not None:
            self._write_manifest(updated)
        if with_command_line_option:
            return f"--load-extension={self.extension_absolute_path}"
        return self.extension_absolute_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write an API key into the NopeCHA Automation Build manifest.json."
    )
    parser.add_argument(
        "extension_dir",
        help="Path to the unpacked Automation Build directory",
    )
    parser.add_argument(
        "--key-env",
        default="NOPECHA_API_KEY",
        help="Environment variable holding the API key (default: NOPECHA_API_KEY)",
    )
    parser.add_argument(
        "--key-stdin",
        action="store_true",
        help="Read the API key from stdin",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write manifest.json. Omit this flag for a dry run",
    )
    return parser


def _cli_api_key(read_stdin: bool, env_name: str) -> str:
    if read_stdin:
        api_key = sys.stdin.read()
        if api_key.endswith("\r\n"):
            api_key = api_key[:-2]
        elif api_key.endswith("\n"):
            api_key = api_key[:-1]
        return api_key
    try:
        return os.environ[env_name]
    except KeyError as exc:
        raise ValueError(f"Environment variable {env_name} is not set") from exc


def _run_cli(read_stdin: bool, env_name: str, extension_dir: str, write: bool) -> dict[str, list[str]]:
    api_key = _validated_api_key(_cli_api_key(read_stdin, env_name))
    extension = Nopecha(api_key=api_key, extension_path=extension_dir)
    if write:
        return extension.update_files()
    report, updated_manifest = extension._plan_update(None)
    if updated_manifest is not None:
        report["modified"].append(_MANIFEST_NAME)
    return report


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = _run_cli(args.key_stdin, args.key_env, args.extension_dir, args.write)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
