"""
Reads SSG configurations from `site.yaml` and merges them with the defaults.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import AsteriaError

# The "minimal" theme shipped with asteria itself (asteria/site/source/
# themes/minimal, relative to this file's own package directory) — the
# fallback SiteConfig.theme_dir uses when a project doesn't have its own
# copy yet, and the source reset_theme() copies back over a project's
# copy when it's been broken by local edits. Both need the exact same
# path, so it's computed once, here.
_BUNDLED_MINIMAL_THEME_DIR = Path(__file__).parent / "site" / "source" / "themes" / "minimal"

DEFAULTS: dict[str, Any] = {
    "site": {
        "title": "My Site",
        "description": "",
        "url": "http://localhost:8000",
        "language": "en",
        "home_page": "welcome",  # id da página usada como index.html
    },
    "content": {
        "pages": "content/pages",
        "posts": "content/posts",
    },
    "output": {
        "directory": "../result",
    },
    "static": {
        "directory": "static",
    },
    "theme": {
        "name": "minimal",
        "directory": "themes",
        # Site-level overrides for theme-exclusive params 
        "params": {},
    },
    
    "nav": [],
    "menu": [],    
    "social": [],
    "blog": {
        "posts_per_page": 10,
        "excerpt_enabled": True,
        "excerpt_length": 280,
    },
    "i18n": {       
        "languages": [],       
        "default_language": "",
        # Site-level override/extension for the theme's own i18n.yaml
        # (UI string translations) — see i18n_strings.load_theme_i18n.
        # Same escape hatch as theme.params for theme.yaml.
        "strings": {},
    },
    "assets": {       
        "fingerprint": True,
    },
    "urls": {
        "pages": "/pages/{slug}/",
        "posts": "/blog/{slug}/",
        "tags": "/tags/{slug}/",
        "categories": "/categories/{slug}/",
        "tags_index": "/tags/",
        "categories_index": "/categories/",
    },
    "feeds": {
        "enabled": True,
        "format": "rss",  # rss | atom
    },
    "search": {
        "enabled": True,
    },
    "sitemap": {
        "enabled": True,
    },
    "robots": {
        "enabled": True,
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merges `override` on top of `base`. Public (no leading
    underscore) because it's also used by theme_config.load_theme_config
    to merge site.yaml's `theme.params` onto theme.yaml — see there.
    """
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class SiteConfig:
    """Site configuration, already merged with the standards."""

    data: dict[str, Any]
    root: Path
    
    @property
    def title(self) -> str:
        return self.data["site"]["title"]

    @property
    def description(self) -> str:
        return self.data["site"]["description"]

    @property
    def url(self) -> str:
        return self.data["site"]["url"].rstrip("/")

    @property
    def language(self) -> str:
        return self.data["site"]["language"]

    @property
    def home_page(self) -> str:
        """
        Home identifier: the `id` of a page, or the word 
        special 'blog'
        """
        return self.data["site"].get("home_page", "inicio")

    @property
    def pages_dir(self) -> Path:
        return self.root / self.data["content"]["pages"]

    @property
    def posts_dir(self) -> Path:
        return self.root / self.data["content"]["posts"]

    @property
    def output_dir(self) -> Path:
        return self.root / self.data["output"]["directory"]

    @property
    def static_dir(self) -> Path:
        return self.root / self.data["static"]["directory"]

    @property
    def theme_name(self) -> str:
        return self.data["theme"]["name"]

    @property
    def _configured_theme_dir(self) -> Path:    
        return self.root / self.data["theme"]["directory"] / self.theme_name

    @property
    def theme_dir(self) -> Path:
        if self._configured_theme_dir.exists():
            return self._configured_theme_dir

        return _BUNDLED_MINIMAL_THEME_DIR

    @property
    def theme_source(self) -> str:
        """'project' ou 'bundled' — useful for diagnostics/CLI."""
        return "project" if self._configured_theme_dir.exists() else "bundled"

    @property
    def nav_config(self) -> list[Any]:
        """Raw `nav:` entries from site.yaml, consumed by nav.build_nav.
        Lives here (not in theme.yaml) because it references page/post
        ids, which is site data — see the note on DEFAULTS above."""
        return self.data.get("nav", [])

    @property
    def menu_config(self) -> list[Any]:
        """Raw `menu:` entries from site.yaml, consumed by
        build._build_menu. Same rationale as `nav_config`."""
        return self.data.get("menu", [])

    @property
    def social_config(self) -> list[Any]:
        """Raw `social:` entries from site.yaml, consumed by
        social.build_social_links."""
        return self.data.get("social", [])

    @property
    def theme_params(self) -> dict[str, Any]:
        """Site-level overrides for theme-exclusive params, deep-merged
        onto theme.yaml by theme_config.load_theme_config. This is the
        escape hatch that lets a theme keep its own private config keys
        (colors, layout switches, ...) while still letting the site
        author tweak them without editing the theme itself."""
        return self.data.get("theme", {}).get("params", {})

    @property
    def posts_per_page(self) -> int:
        return int(self.data["blog"]["posts_per_page"])

    @property
    def excerpt_enabled(self) -> bool:
        return self.data["blog"]["excerpt_enabled"]

    @property
    def excerpt_length(self) -> int:
        return int(self.data["blog"]["excerpt_length"])

    @property
    def default_language(self) -> str:        
        return self.data["i18n"].get("default_language") or self.language

    @property
    def languages(self) -> list[str]:
        
        default = self.default_language
        extra = [lang for lang in (self.data["i18n"].get("languages") or []) if lang != default]
        return [default, *extra]

    @property
    def i18n_string_overrides(self) -> dict[str, Any]:
        """Site-level override/extension for the theme's UI string
        translations (`i18n.yaml` inside the theme directory) — see
        i18n_strings.load_theme_i18n."""
        return self.data["i18n"].get("strings") or {}

    @property
    def fingerprint_assets_enabled(self) -> bool:
        return bool(self.data.get("assets", {}).get("fingerprint", True))

    @property
    def blog_index_url(self) -> str:
        """URL of the paginated blog listing ("/blog/", "/blog/page/2/",
        ...), derived from `urls.posts` (e.g. "/blog/{slug}/" -> "/blog/")."""

        posts_pattern = self.data["urls"]["posts"]
        prefix = re.sub(r"/+", "/", posts_pattern.replace("{slug}", "")).strip("/")
        return f"/{prefix}/" if prefix else "/"

    @property
    def url_patterns(self) -> dict[str, str]:
        return self.data["urls"]

    @property
    def feeds_enabled(self) -> bool:
        return bool(self.data["feeds"].get("enabled", True))

    @property
    def search_enabled(self) -> bool:
        """Controla a geração de `search-index.json` (e variantes por
        idioma, ex: `pt-search-index.json`) — um array JSON de
        `{title, url, date, excerpt}` para cada page/post, consumido por
        JS de busca client-side em temas que esperam esse formato. O
        Asteria não fornece UI/JS de busca; só o índice de dados — ver
        build._write_search_index."""
        return bool(self.data["search"].get("enabled", True))

    @property
    def sitemap_enabled(self) -> bool:
        return bool(self.data["sitemap"].get("enabled", True))

    @property
    def robots_enabled(self) -> bool:
        return bool(self.data["robots"].get("enabled", True))


def load_config(config_path: Path) -> SiteConfig:
    if not config_path.exists():
        raise AsteriaError(f"Configuration file not found: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise AsteriaError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise AsteriaError(f"The content of {config_path} must be a YAML mapping.")

    merged = deep_merge(DEFAULTS, raw)
    return SiteConfig(data=merged, root=config_path.parent.resolve())


def reset_theme(project_root: Path) -> Path:
    """Restores the bundled "minimal" theme to
    `<project_root>/source/themes/minimal`, overwriting any local edits
    to files the bundled theme also ships. Creates `source/themes/`
    (and `source/`, if somehow missing) when it doesn't exist yet.
    """
    if not _BUNDLED_MINIMAL_THEME_DIR.exists():
        raise AsteriaError(
            f"Bundled theme not found at {_BUNDLED_MINIMAL_THEME_DIR} "
            "— the asteria installation looks broken."
        )

    destination = project_root / "source" / "themes" / "minimal"
    shutil.copytree(_BUNDLED_MINIMAL_THEME_DIR, destination, dirs_exist_ok=True)
    return destination