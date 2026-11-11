"""
Site menu: the list of items a theme should link to.

A page entry's label comes from the referenced document itself
(`menu_title:` > `title:` in its front matter), already in the right
language. The legacy form `- page: welcome` (with an optional `title:`
override) is still accepted, with a deprecation warning.
"""

from __future__ import annotations

from typing import Any

from .document import Page
from .errors import Diagnostics
from .i18n_strings import translate
from .urls import prefix_lang

# Reserved reference meaning "the blog index" — also accepted by
# `site.home_page`. The blog's URL is derived from `urls.posts`
# (see SiteConfig.blog_index_url).
BLOG_KEY = "blog"


def resolve_page_reference(
    ref: str,
    pages_by_id: dict[str, Page],
    pages_by_translation_key: dict[str, dict[str, Page]],
    lang: str,
    default_language: str,
) -> Page | None:
    """translation_key is checked FIRST, exact id second. For a
    translation group: `lang`, then the default language, then any."""
    translations = pages_by_translation_key.get(ref)
    if translations:
        return (
            translations.get(lang)
            or translations.get(default_language)
            or next(iter(translations.values()))
        )
    return pages_by_id.get(ref)


def _split_entry(raw: Any) -> tuple[str, str | None, bool] | None:
    """Returns (reference, title_override, is_legacy), or None if malformed."""
    # `int` because YAML turns an id like `404` into a number.
    if isinstance(raw, (str, int)) and not isinstance(raw, bool):
        return str(raw), None, False
    if isinstance(raw, dict) and isinstance(raw.get("page"), (str, int)):
        return str(raw["page"]), raw.get("title"), True
    return None


def menu_references(menu_config: list[Any]) -> set[str]:
    """Every reference named in the menu (used to cross-check `home_page`)."""
    refs = (_split_entry(raw) for raw in menu_config)
    return {parts[0] for parts in refs if parts is not None}


def build_menu(
    menu_config: list[Any],
    default_language: str,
    blog_index_url: str,
    pages_by_id: dict[str, Page],
    pages_by_translation_key: dict[str, dict[str, Page]],
    lang: str,
    diagnostics: Diagnostics,
    theme_strings: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """Builds the menu for a single language."""
    items: list[dict[str, str]] = []

    for raw in menu_config:
        parts = _split_entry(raw)
        if parts is None:
            diagnostics.warning(f"menu: malformed item, ignored: {raw!r}", source="site.yaml")
            continue

        ref, title_override, legacy = parts
        if legacy:
            diagnostics.warning(
                f"menu: '- page: {ref}' is deprecated, use '- {ref}'.", source="site.yaml"
            )

        if ref == BLOG_KEY:
            url = prefix_lang(blog_index_url, lang, default_language)
            title = title_override or translate(
                theme_strings, "blog_menu_label", lang, default_language, fallback="Blog"
            )
        else:
            page = resolve_page_reference(
                ref, pages_by_id, pages_by_translation_key, lang, default_language
            )
            if page is None:
                diagnostics.warning(
                    f"menu: page '{ref}' not found (checked both as an "
                    "exact page id and as a translation_key).",
                    source="site.yaml",
                )
                url = "#"
                title = title_override or ref
            else:
                url = page.url
                title = title_override or page.menu_title or page.title

        items.append({"title": title, "url": url, "page_id": ref})

    return items