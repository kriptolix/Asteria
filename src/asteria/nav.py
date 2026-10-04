"""
Configurable hierarchical navigation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import Diagnostics
from .references import build_translation_registry


@dataclass
class NavEntry:
    title: str
    url: str | None = None
    children: list["NavEntry"] = field(default_factory=list)


def _resolve_target(
    page_id: str,
    registry: dict[str, Any],
    translation_registry: dict[str, dict[str, Any]],
    lang: str,
    default_language: str,
) -> Any | None:
    """translation_key is checked FIRST, exact id second — same rationale
    as build._build_menu and references.resolve_references: a translated
    page's translation_key (e.g. "about") is usually identical to the
    untranslated/default page's own id, so checking id first would always
    match the default-language page and never reach the translation
    group. A dotted id used to pin one specific translation (e.g.
    "about.pt") is never itself a valid translation_key, so this order
    never breaks that escape hatch."""
    group = translation_registry.get(page_id)
    if group:
        return (
            group.get(lang)
            or group.get(default_language)
            or next(iter(group.values()))
        )
    return registry.get(page_id)


def _title_for(target: Any) -> str:
    """A `nav:` entry's label always comes from the resolved document
    itself, never from site.yaml — that's the whole reason `nav_title:`
    (front matter) exists: a label exclusive to the nav, distinct from
    the document's real `title:`, and already translated per-document
    like any other front matter field. `getattr` guards raw pages
    (RawPage has no front matter / nav_title at all), which fall
    straight through to `target.title`."""
    return getattr(target, "nav_title", None) or target.title


def _resolve(
    page_id: str,
    registry: dict[str, Any],
    translation_registry: dict[str, dict[str, Any]],
    lang: str,
    default_language: str,
    diagnostics: Diagnostics,
) -> NavEntry:
    target = _resolve_target(page_id, registry, translation_registry, lang, default_language)
    if target is None:
        diagnostics.warning(
            f"nav: Non-existent item reference ID: '{page_id}'.", source="site.yaml"
        )
        return NavEntry(title=page_id, url=None)
    return NavEntry(title=_title_for(target), url=target.url)


def _parse_items(
    items: list[Any],
    registry: dict[str, Any],
    translation_registry: dict[str, dict[str, Any]],
    lang: str,
    default_language: str,
    diagnostics: Diagnostics,
) -> list[NavEntry]:
    """`items` is `nav:` (or a nested branch of it): each entry is either
    a bare document id (a leaf), or a single-key mapping `{id: [...]}`
    whose key is a document id and whose value is a list of children (a
    branch) — nestable to any depth the same way, e.g.:

        nav:
          - "introducao":
            - "basico"
            - "personagens":
              - "criacao_personagem"
              - "arquetipos"

    There is no site.yaml-level title anywhere in this format: a
    branch's key is resolved as a page id exactly like a leaf is, and
    its label comes from that same resolved document — see
    `_title_for`. The key is never treated as literal display text."""
    result: list[NavEntry] = []

    for raw in items:
        if isinstance(raw, str):
            result.append(
                _resolve(raw, registry, translation_registry, lang, default_language, diagnostics)
            )
            continue

        if isinstance(raw, dict) and len(raw) == 1:
            (index_id, value), = raw.items()

            if not isinstance(index_id, str) or not isinstance(value, list):
                diagnostics.warning(
                    "nav: a branch must be a single page ID mapping to a "
                    f"list of children — ignored: {raw!r}",
                    source="site.yaml",
                )
                continue

            target = _resolve_target(
                index_id, registry, translation_registry, lang, default_language
            )
            if target is None:
                diagnostics.warning(
                    f"nav: Non-existent item reference ID: '{index_id}'.", source="site.yaml"
                )
                continue

            children = _parse_items(
                value, registry, translation_registry, lang, default_language, diagnostics
            )
            result.append(NavEntry(title=_title_for(target), url=target.url, children=children))
            continue

        diagnostics.warning(f"nav: malformed item, ignored: {raw!r}", source="site.yaml")

    return result


def build_nav(
    nav_config: list[Any],
    registry: dict[str, Any],
    diagnostics: Diagnostics,
    translation_registry: dict[str, dict[str, Any]] | None = None,
    lang: str = "",
    default_language: str = "",
) -> list[NavEntry]:
    """Builds the nav tree for a single language. `nav_config` is a list
    of document ids only — a bare id is a leaf, a single-key mapping
    `{id: [...]}` is a branch, nestable to any depth; see `_parse_items`.
    There is no way to write a title directly in site.yaml, branch key
    included: every entry's label comes from the resolved document's own
    `nav_title:` front matter field, falling back to its `title:` (see
    `_title_for`) — unlike a title hardcoded in site.yaml, this is
    naturally per-language, since each translation has its own front
    matter.
    """
    return _parse_items(
        nav_config or [], registry, translation_registry or {}, lang, default_language, diagnostics
    )