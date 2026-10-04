"""
Theme-owned UI string translations (e.g. "min de leitura", "Leia mais").

Distinct from dates.py: that module hardcodes universal calendar data
(month names) inside Asteria itself, because every site written in a
given language needs the same month names — that's not something a site
or theme author should have to redeclare. UI copy is different: it's the
theme's own wording, written by the theme author, and a site author may
reasonably want to override it or add a language it doesn't ship. So it
lives as *data*, not code — same as theme.yaml: an `i18n.yaml` file
inside the theme's own directory, one top-level key per language,
optionally deep-merged with an `i18n.strings` override in site.yaml
(mirrors how `theme.params` overrides theme.yaml — see theme_config.py).

    # themes/<name>/i18n.yaml
    pt:
      reading_time: "{minutes} min de leitura"
    en:
      reading_time: "{minutes} min read"

    # site.yaml, optional — extends/overrides the theme's own i18n.yaml
    i18n:
      strings:
        pt:
          reading_time: "{minutes} minutos de leitura"

Used in a template via the `t()` global (registered in
templating.create_environment):

    {{ t("reading_time", post.lang, minutes=post.reading_time) }}
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import deep_merge
from .errors import AsteriaError


def load_theme_i18n(
    theme_dir: Path, site_overrides: dict[str, Any] | None = None
) -> dict[str, dict[str, str]]:
    """Loads `<theme_dir>/i18n.yaml` and deep-merges `site_overrides`
    (site.yaml's `i18n.strings`) on top of it — same pattern as
    theme_config.load_theme_config. A theme without an i18n.yaml simply
    has no theme-provided strings (not an error): plenty of themes won't
    need this at all."""
    path = theme_dir / "i18n.yaml"
    if not path.exists():
        theme_strings: dict[str, Any] = {}
    else:
        try:
            theme_strings = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise AsteriaError(f"Invalid YAML in {path}: {exc}") from exc
        if not isinstance(theme_strings, dict):
            raise AsteriaError(f"The content of {path} must be a YAML mapping.")

    return deep_merge(theme_strings, site_overrides or {})


def translate(
    strings: dict[str, dict[str, str]],
    key: str,
    lang: str,
    default_language: str,
    fallback: str | None = None,
    **kwargs: Any,
) -> str:
    """Looks up `strings[lang][key]`, falling back to
    `strings[default_language][key]` when `lang` has no translation for
    that key — same "current language, then default language" fallback
    used everywhere else per-language content is resolved (menu, nav,
    references). `**kwargs` are interpolated via `str.format`, e.g.
    `minutes=5` for a template string like "{minutes} min de leitura".

    When the key is missing from every language, returns `fallback` if
    one was given — for a caller that has a sensible built-in English
    (or otherwise reasonable) default and only wants the theme's
    `i18n.yaml` to be able to override it, not required to define it at
    all (see build._build_menu's use for the "blog" menu entry's label).
    Without a `fallback`, returns the key itself wrapped in `??...??` —
    visible enough in the rendered page to be noticed and fixed, instead
    of silently showing nothing. Unlike a broken `[[reference]]`, a
    missing UI string is deliberately never a build error: one
    missing/mistyped translation key shouldn't block an entire build."""
    template = strings.get(lang, {}).get(key) or strings.get(default_language, {}).get(key)
    if template is None:
        return fallback if fallback is not None else f"??{key}??"
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        # A malformed template (referencing a placeholder that wasn't
        # passed) shouldn't break the page either — show it unformatted
        # so the problem is visible instead of raising.
        return template