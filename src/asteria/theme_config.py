"""
Theme-specific settings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import SiteConfig, deep_merge
from .errors import AsteriaError


def _read_theme_defaults(theme_dir: Path) -> dict[str, Any]:
    """Reads `theme.yaml` from `theme_dir`. Returns {} if the file is absent."""
    path = theme_dir / "theme.yaml"
    if not path.exists():
        return {}

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise AsteriaError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise AsteriaError(f"The content of {path} must be a YAML mapping.")
    return data


def load_theme_config(
    theme_dir: Path, site_overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Loads theme.yaml and deep-merges `site_overrides` on top of it."""
    return deep_merge(_read_theme_defaults(theme_dir), site_overrides or {})


@dataclass
class ThemeConfig:
    """What the active theme's own `theme.yaml` contains.
    """

    name: str
    source: str  # "project" or "bundled" (see SiteConfig.theme_source)
    directory: Path
    data: dict[str, Any] = field(default_factory=dict)


def theme_config_from_site(config: SiteConfig) -> ThemeConfig:
    """Builds the ThemeConfig for the theme selected by `config`."""
    theme_dir = config.theme_dir
    return ThemeConfig(
        name=config.theme_name,
        source=config.theme_source,
        directory=theme_dir,
        data=_read_theme_defaults(theme_dir),
    )