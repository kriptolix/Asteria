"""
Semantic reference resolution.

Handles [[id]] / [[id|Custom label]] cross-references between pages/posts.
Raw HTML embedding is NOT handled here — that's a `:::html ... :::` fenced
block recognized directly by the odt2web converter, before this module
ever sees the HTML.
"""

from __future__ import annotations

import re
from html import escape
from typing import Any

from .errors import Diagnostics

# Allows a dot in the id (e.g. "hello-world.pt") so a specific translation
# can be pinned by its exact document id — see _resolve_target below for
# why that alone isn't the primary resolution path.
REFERENCE_RE = re.compile(r"(\\)?\[\[([A-Za-z0-9_.\-]+)(?:\|([^\]]+))?\]\]")

MORE_MARKER = "more" 

_MORE_BLOCK_RE = re.compile(r"\s*<p>\s*\[\[more\]\]\s*</p>\s*", re.IGNORECASE)

_MORE_INLINE_RE = re.compile(r"\[\[more\]\]", re.IGNORECASE)



def build_registry(items: list[Any]) -> dict[str, Any]:
    
    return {item.id: item for item in items}


def build_translation_registry(items: list[Any]) -> dict[str, dict[str, Any]]:
    """Groups items by translation_key -> {lang: item}, so a plain
    [[reference]] can be resolved to the version matching the *current*
    document's language, instead of always landing on whichever
    translation happens to own that exact id.

    Items without a translation_key/lang (e.g. raw pages) are skipped —
    they're still reachable by their exact id through the regular
    registry built by `build_registry`."""
    registry: dict[str, dict[str, Any]] = {}
    for item in items:
        translation_key = getattr(item, "translation_key", None)
        lang = getattr(item, "lang", None)
        if not translation_key or not lang:
            continue
        registry.setdefault(translation_key, {})[lang] = item
    return registry


def resolve_references(
    html: str,
    registry: dict[str, Any],
    source: str,
    diagnostics: Diagnostics,
    translation_registry: dict[str, dict[str, Any]] | None = None,
    lang: str = "",
    default_language: str = "",
) -> str:
    def _resolve_target(ref_id: str) -> Any | None:
        # translation_key is checked FIRST, exact id second — mirrors
        # build._build_menu's `page:` resolution, and for the same
        # reason: a translated document's translation_key (e.g.
        # "about") is usually identical to the untranslated/default
        # document's own id, so checking id first would always match the
        # default-language document and never reach the translation
        # group. A dotted id used to pin one specific translation (e.g.
        # "about.pt") is never itself a valid translation_key, so this
        # order never breaks that escape hatch.
        if translation_registry:
            group = translation_registry.get(ref_id)
            if group:
                return (
                    group.get(lang)
                    or group.get(default_language)
                    or next(iter(group.values()))
                )
        return registry.get(ref_id)

    def _replace(match: re.Match) -> str:
        is_escaped = bool(match.group(1))
        ref_id = match.group(2)
        label = match.group(3)

        if is_escaped:
            suffix = f"|{label}" if label else ""
            return f"[[{ref_id}{suffix}]]"

        if ref_id.lower() == MORE_MARKER:
            # [[more]] is a reserved marker, not a cross-reference — it's
            # handled later, per-post, by split_at_more_marker() to build
            # the excerpt/preview split. REFERENCE_RE matches it too
            # (any [[...]] with an alphanumeric id), so without this
            # check it would be treated as a broken reference to a
            # nonexistent document with id "more": resolve_references_for_all()
            # runs before split_at_more_marker() in run_build(), so the
            # marker would already be replaced with a
            # `broken-reference` span (and, since target-not-found is a
            # diagnostics ERROR, would abort the whole build) before
            # split_at_more_marker ever got a chance to see it. Left
            # untouched here, it survives verbatim to that later step.
            return match.group(0)

        target = _resolve_target(ref_id)

        if target is None:
            diagnostics.error(
                f"[[{ref_id}]]: Target of reference not found.",
                source=source,
            )
            # Keep it visible in the HTML to make it easier to spot the problem,
            # instead of silently making the author's text disappear.
            return f'<span class="broken-reference" title="Not found: {escape(ref_id)}">[[{escape(ref_id)}]]</span>'

        text = label.strip() if label else target.title
        return f'<a href="{target.url}">{escape(text)}</a>'

    return REFERENCE_RE.sub(_replace, html)


def resolve_references_for_all(
    documents: list[Any],
    diagnostics: Diagnostics,
    extra_targets: list[Any] | None = None,
    default_language: str = "",
) -> None:
    
    registry = build_registry(documents)
    if extra_targets:
        registry.update(build_registry(extra_targets))

    translation_registry = build_translation_registry(documents)

    for doc in documents:
        doc.content_html = resolve_references(
            doc.content_html,
            registry,
            source=str(doc.source_path),
            diagnostics=diagnostics,
            translation_registry=translation_registry,
            lang=getattr(doc, "lang", "") or default_language,
            default_language=default_language,
        )


def split_at_more_marker(html: str) -> tuple[str, str | None]:
    """
    Manual preview of posts 
    """
    match = _MORE_BLOCK_RE.search(html)
    if match:
        preview_html = html[: match.start()]
        full_html = html[: match.start()] + html[match.end() :]
        return full_html, preview_html
 
    match = _MORE_INLINE_RE.search(html)
    if match:
        preview_html = html[: match.start()]
        full_html = html[: match.start()] + html[match.end() :]
        return full_html, preview_html
 
    return html, None