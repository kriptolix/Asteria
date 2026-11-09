"""
Editing and saving of a project's settings

Typical flow, on the "Sync" button:

    settings = ProjectSettings.load(project_root)
    settings.theme.data["default_variant"] = "dark"     # UI -> dataclasses
    settings.site.data["site"]["title"] = "My blog"
    settings.save()                                     # dataclasses -> files
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any


import yaml  
from gi.repository import Gio, GLib  

from .asteria.api import (  
    AsteriaError,
    SiteConfig,
    ThemeConfig,
    load_project_config,
    load_project_theme,
)


class ThemeNotEditableError(AsteriaError):
    """The theme has pending changes but is the bundled one, which must not
    be written."""


# --------------------------------------------------------------- YAML helpers


def apply_changes(target: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> None:
    """Replays on `target` the differences between `before` and `after`.   
    """
    for key in before:
        if key not in after:
            target.pop(key, None)

    for key, new_value in after.items():
        if key in before and before[key] == new_value:
            continue
        old_value = before.get(key)
        if isinstance(new_value, dict) and isinstance(old_value, dict):
            child = target.get(key)
            if not isinstance(child, dict):
                child = target[key] = {}
            apply_changes(child, old_value, new_value)
        else:
            target[key] = copy.deepcopy(new_value)


def serialize_yaml(data: dict[str, Any]) -> str:
    """Serializes a mapping to YAML text and verifies it parses back to
    exactly the same data, so invalid values are caught before anything is
    written to disk. Comments of an original file are not preserved.
    """
    try:
        text = yaml.safe_dump(
            data, sort_keys=False, allow_unicode=True, default_flow_style=False
        )
        reparsed = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise AsteriaError(f"Settings cannot be serialized to YAML: {exc}") from exc

    if reparsed != data:
        raise AsteriaError("Settings failed the YAML round-trip check.")
    return text


# ------------------------------------------------------------------ 


def _read_bytes(file: Gio.File) -> bytes | None:
    """Current content of `file`, or None if it does not exist."""
    try:
        _ok, contents, _etag = file.load_contents(None)
    except GLib.Error as exc:
        if exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND):
            return None
        raise AsteriaError(f"Could not read {file.get_path()}: {exc.message}") from exc
    return bytes(contents)


def _replace(file: Gio.File, payload: bytes, make_backup: bool) -> None:
    """Atomically replaces `file`: Gio writes a temporary file and renames
    it over the target, so a crash leaves the old or the new content, never
    a truncated file."""
    try:
        file.replace_contents(
            payload,
            None,  # etag: no conflict check, the dataclasses are the source of truth
            make_backup,
            Gio.FileCreateFlags.NONE,
            None,  # cancellable
        )
    except GLib.Error as exc:
        raise AsteriaError(f"Could not write {file.get_path()}: {exc.message}") from exc


def _restore(file: Gio.File, previous: bytes | None) -> None:
    """Puts `file` back to what it was before a save."""
    if previous is None:
        try:
            file.delete(None)
        except GLib.Error as exc:
            raise AsteriaError(exc.message) from exc
    else:
        _replace(file, previous, make_backup=False)


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    """The file's content as a mapping, WITHOUT any defaults merged in."""
    raw = _read_bytes(Gio.File.new_for_path(str(path)))
    if raw is None:
        return {}
    try:
        data = yaml.safe_load(raw.decode("utf-8")) or {}
    except yaml.YAMLError as exc:
        raise AsteriaError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AsteriaError(f"The content of {path} must be a YAML mapping.")
    return data


# -------------------------------------------------------------- ProjectSettings


class ProjectSettings:
    """A project's `site.yaml` and `theme.yaml`, loaded for editing.    

    `site.data` is the configuration merged with the defaults. To keep the
    defaults out of `site.yaml`, the file's own content is kept aside and
    only the keys that changed are applied to it when saving.
    """

    def __init__(
        self,
        site: SiteConfig,
        theme: ThemeConfig,
        site_path: Path,
        site_raw: dict[str, Any],
    ) -> None:
        # The library builds `site.data` sharing nested objects with its
        # DEFAULTS; detach it, since this class lets callers edit it in place.
        site.data = copy.deepcopy(site.data)

        self.site = site
        self.theme = theme
        self.site_path = site_path
        self._site_raw = site_raw
        self._site_original = copy.deepcopy(site.data)
        self._theme_original = copy.deepcopy(theme.data)

    @classmethod
    def load(cls, project_root: Path, config_filename: str = "site.yaml") -> "ProjectSettings":
        site = load_project_config(project_root, config_filename)
        theme = load_project_theme(project_root, config_filename)
        site_path = project_root / "source" / config_filename
        return cls(site, theme, site_path, _read_yaml_mapping(site_path))

    # ------------------------------------------------------------------ state

    @property
    def theme_path(self) -> Path:
        return self.theme.directory / "theme.yaml"

    @property
    def site_modified(self) -> bool:
        return self.site.data != self._site_original

    @property
    def theme_modified(self) -> bool:
        return self.theme.data != self._theme_original

    @property
    def modified(self) -> bool:
        return self.site_modified or self.theme_modified

    def _pending_site_raw(self) -> dict[str, Any]:
        pending = copy.deepcopy(self._site_raw)
        apply_changes(pending, self._site_original, self.site.data)
        return pending

    # ----------------------------------------------------------------- saving

    def save(self, make_backup: bool = False) -> list[Path]:
        """Writes whichever of `theme.yaml` / `site.yaml` has pending changes
        and returns the paths written (empty if nothing was modified).        
        """
        pending: list[tuple[Path, str]] = []
        theme_pending = self.theme_modified
        new_site_raw: dict[str, Any] | None = None

        if theme_pending:
            if self.theme.source != "project":
                raise ThemeNotEditableError(
                    f"Theme '{self.theme.name}' is the bundled one and cannot be modified. "
                    "Copy it into the project first."
                )
            pending.append((self.theme_path, serialize_yaml(self.theme.data)))

        if self.site_modified:
            new_site_raw = self._pending_site_raw()
            pending.append((self.site_path, serialize_yaml(new_site_raw)))

        written: list[tuple[Gio.File, bytes | None]] = []  # (file, previous content)
        try:
            for path, text in pending:
                file = Gio.File.new_for_path(str(path))
                previous = _read_bytes(file)
                _replace(file, text.encode("utf-8"), make_backup)
                written.append((file, previous))
        except AsteriaError as exc:
            failed_restores = []
            for file, previous in reversed(written):
                try:
                    _restore(file, previous)
                except AsteriaError:
                    failed_restores.append(file.get_path())
            if failed_restores:
                raise AsteriaError(
                    f"{exc} Additionally, these files could not be restored and may be "
                    f"inconsistent: {', '.join(failed_restores)}"
                ) from exc
            raise

        # Everything is on disk: the current state becomes the new baseline.
        if theme_pending:
            self._theme_original = copy.deepcopy(self.theme.data)
        if new_site_raw is not None:
            self._site_raw = new_site_raw
            self._site_original = copy.deepcopy(self.site.data)
        return [path for path, _text in pending]