"""
Theme-specific settings
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import deep_merge
from .errors import AsteriaError


def load_theme_config(
    theme_dir: Path, site_overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Loads theme.yaml and deep-merges `site_overrides` on top of it."""
    path = theme_dir / "theme.yaml"
    if not path.exists():
        theme_defaults: dict[str, Any] = {}
    else:
        try:
            theme_defaults = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise AsteriaError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(theme_defaults, dict):
            raise AsteriaError(f"The content of {path} must be a YAML mapping.")

    return deep_merge(theme_defaults, site_overrides or {})